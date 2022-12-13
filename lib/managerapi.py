import requests
from .errors import raise_bimcloud_manager_error, HttpError
from .url import is_url, join_url

class ManagerApi:
	def __init__(self, manager_url):
		if not is_url(manager_url):
			raise ValueError('Manager url is invalid.')

		self.manager_url = manager_url
		self._api_root = join_url(manager_url, 'management/client')

	def create_session(self, username, password, client_id):
		request = {
			'username': username,
			'password': password,
			'client-id': client_id
		}
		url = join_url(self._api_root, 'create-session')
		response = requests.post(url, json=request)
		result = self.process_response(response)
		# We can ignore expire-timeout for now. It will have effect on future versions of the API.
		return result['user-id'], result['session-id']

	def close_session(self, session_id):
		url = join_url(self._api_root, 'close-session')
		response = requests.post(url, params={ 'session-id': session_id })
		self.process_response(response)

	def ping_session(self, session_id):
		url = join_url(self._api_root, 'ping-session')
		response = requests.post(url, params={ 'session-id': session_id })
		self.process_response(response)

	def get_resource(self, session_id, by_path=None, by_id=None, try_get=False):
		if by_id is not None:
			return self.get_resource_by_id(session_id, by_id)

		criterion = None

		if by_path is not None:
			criterion = { '$eq': { '$path': by_path } }

		try:
			return self.get_resource_by_criterion(session_id, criterion)
		except Exception as err:
			if try_get:
				return None
			raise err

	def get_resource_by_id(self, session_id, resource_id):
		if resource_id is None:
			raise ValueError('"resource_id"" expected.')

		url = join_url(self._api_root, 'get-resource')
		response = requests.get(url, params={ 'session-id': session_id, 'resource-id': resource_id })
		result = self.process_response(response)
		return result

	def get_resources_by_criterion(self, session_id, criterion, options=None):
		if criterion is None:
			raise ValueError('"criterion"" expected.')

		url = join_url(self._api_root, 'get-resources-by-criterion')
		params = { 'session-id': session_id }
		if isinstance(options, dict):
			for key in options:
				params[key] = options[key]

		response = requests.post(url, params=params, json=criterion)
		result = self.process_response(response)
		assert isinstance(result, list), 'Result is not a list.'
		return result

	def get_resource_by_criterion(self, session_id, criterion, options=None):
		result = self.get_resources_by_criterion(session_id, criterion, options)
		return result[0] if result else None

	def create_resource_group(self, session_id, name, parent_id=None):
		url = join_url(self._api_root, 'insert-resource-group')
		directory = {
			'name': name,
			'type': 'resourceGroup'
		}
		response = requests.post(url, params={ 'session-id': session_id, 'parent-id': parent_id }, json=directory)
		result = self.process_response(response)
		assert isinstance(result, str), 'Result is not a string.'
		return result

	def delete_resource_group(self, session_id, directory_id):
		url = join_url(self._api_root, 'delete-resource-group')
		response = requests.delete(url, params={ 'session-id': session_id, 'resource-id': directory_id })
		result = self.process_response(response)
		return result

	def delete_resources_by_id_list(self, session_id, ids):
		url = join_url(self._api_root, 'delete-resources-by-id-list')
		response = requests.post(url, params={ 'session-id': session_id }, json={ 'ids': ids })
		result = self.process_response(response)
		return result

	def delete_blob(self, session_id, blob_id):
		url = join_url(self._api_root, 'delete-blob')
		response = requests.delete(url, params={ 'session-id': session_id, 'resource-id': blob_id })
		self.process_response(response)

	def update_blob(self, session_id, blob):
		url = join_url(self._api_root, 'update-blob')
		response = requests.put(url, params={ 'session-id': session_id }, json=blob)
		self.process_response(response)

	def update_blob_parent(self, session_id, blob_id, body):
		url = join_url(self._api_root, 'update-blob-parent')
		response = requests.post(url, params={ 'session-id': session_id, 'blob-id': blob_id }, json=body)
		self.process_response(response)

	def get_blob_changes_for_sync(self, session_id, path, resource_group_id, from_revision):
		url = join_url(self._api_root, 'get-blob-changes-for-sync')
		request = {
 			'path': path,
			'resourceGroupId': resource_group_id,
			'fromRevision': from_revision
		}
		response = requests.post(url, params={ 'session-id': session_id }, json=request)
		result = self.process_response(response)
		assert isinstance(result, object), 'Result is not an object.'
		return result

	def get_inherited_default_blob_server_id(self, session_id, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-blob-server-id')
		response = requests.get(url, params={ 'session-id': session_id, 'resource-group-id': resource_group_id })
		result = self.process_response(response)
		return result

	def get_job(self, session_id, job_id):
		url = join_url(self._api_root, 'get-job')
		response = requests.get(url, params={ 'session-id': session_id, 'job-id': job_id })
		result = self.process_response(response)
		return result

	def abort_job(self, session_id, job_id):
		url = join_url(self._api_root, 'get-job')
		response = requests.post(url, params={ 'session-id': session_id, 'job-id': job_id })
		result = self.process_response(response)
		return result

	def get_ticket(self, session_id, resource_id):
		url = join_url(self._api_root, 'ticket-generator/get-ticket')
		request = {
			'type': 'freeTicket',
			'resources': [resource_id],
			'format': 'base64'
		}
		response = requests.post(url, params={ 'session-id': session_id }, json=request)
		result = self.process_response(response, json=False)
		assert isinstance(result, bytes), 'Result is not a bytes.'
		result = result.decode('utf-8')
		return result

	@staticmethod
	def process_response(response, json=True):
		# ok, status_code, reason, 430: error-code, error-message
		has_content = response.content is not None and len(response.content)
		if response.ok:
			if has_content:
				return response.json() if json else response.content
			else:
				return None
		if response.status_code == 430:
			# 430: BIMcloud Error
			assert has_content, 'BIMcloud error should has contet.'
			raise_bimcloud_manager_error(response.json())
		raise HttpError(response)