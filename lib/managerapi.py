import requests
from .errors import raise_bimcloud_manager_error, HttpError
from .url import is_url, join_url

class ManagerApi:
	def __init__(self, manager_url):
		if not is_url(manager_url):
			raise ValueError('Manager url is invalid.')

		self.manager_url = manager_url
		self._api_root = join_url(manager_url, 'management/client')

	def get_token_by_password_grant(self, username, password, client_id):
		request = {
			'grant_type': 'password',
			'username': username,
			'password': password,
			'client_id': client_id
		}
		url = join_url(self._api_root, 'oauth2', 'token')
		response = requests.post(url, data=request, headers={ 'Content-Type': 'application/x-www-form-urlencoded' })
		result = self.process_response(response)
		return result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['refresh_token_exp'], result['token_type']

	def get_token_by_refresh_token_grant(self, refresh_token, client_id):
		request = {
			'grant_type': 'refresh_token',
			'refresh_token': refresh_token,
			'client_id': client_id
		}
		url = join_url(self._api_root, 'oauth2', 'token')
		response = requests.post(url, data=request, headers={ 'Content-Type': 'application/x-www-form-urlencoded' })
		result = self.process_response(response)
		return result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['refresh_token_exp'], result['token_type']

	def get_resource(self, access_token, by_path=None, by_id=None, try_get=False):
		if by_id is not None:
			return self.get_resource_by_id(access_token, by_id)

		criterion = None
		if by_path is not None:
			criterion = { '$eq': { '$path': by_path } }

		try:
			return self.get_resource_by_criterion(access_token, criterion)
		except Exception as err:
			if try_get:
				return None
			raise err

	def get_resource_by_id(self, access_token, resource_id):
		if resource_id is None:
			raise ValueError('"resource_id"" expected.')

		url = join_url(self._api_root, 'get-resource')
		response = requests.get(url, params={ 'resource-id': resource_id }, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		return result

	def get_resources_by_criterion(self, access_token, criterion, options=None):
		if criterion is None:
			raise ValueError('"criterion"" expected.')

		url = join_url(self._api_root, 'get-resources-by-criterion')
		params = {}
		if isinstance(options, dict):
			for key in options:
				params[key] = options[key]

		response = requests.post(url, params=params, json=criterion, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		assert isinstance(result, list), 'Result is not a list.'
		return result

	def get_resource_by_criterion(self, access_token, criterion, options=None):
		result = self.get_resources_by_criterion(access_token, criterion, options)
		return result[0] if result else None

	def create_resource_group(self, access_token, name, parent_id=None):
		url = join_url(self._api_root, 'insert-resource-group')
		directory = {
			'name': name,
			'type': 'resourceGroup'
		}
		response = requests.post(url, params={ 'parent-id': parent_id }, json=directory, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		assert isinstance(result, str), 'Result is not a string.'
		return result

	def delete_resource_group(self, access_token, directory_id):
		url = join_url(self._api_root, 'delete-resource-group')
		response = requests.delete(url, params={ 'resource-id': directory_id }, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		return result

	def delete_resources_by_id_list(self, access_token, ids):
		url = join_url(self._api_root, 'delete-resources-by-id-list')
		response = requests.post(url, json={ 'ids': ids }, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		return result

	def delete_blob(self, access_token, blob_id):
		url = join_url(self._api_root, 'delete-blob')
		response = requests.delete(url, params={'resource-id': blob_id }, headers={ 'Authorization': f'Bearer {access_token}' })
		self.process_response(response)

	def update_blob(self, access_token, blob):
		url = join_url(self._api_root, 'update-blob')
		response = requests.put(url, json=blob, headers={ 'Authorization': f'Bearer {access_token}' })
		self.process_response(response)

	def update_blob_parent(self, access_token, blob_id, body):
		url = join_url(self._api_root, 'update-blob-parent')
		response = requests.post(url, params={ 'blob-id': blob_id }, json=body, headers={ 'Authorization': f'Bearer {access_token}' })
		self.process_response(response)

	def get_blob_changes_for_sync(self, access_token, path, resource_group_id, from_revision):
		url = join_url(self._api_root, 'get-blob-changes-for-sync')
		request = {
 			'path': path,
			'resourceGroupId': resource_group_id,
			'fromRevision': from_revision
		}
		response = requests.post(url, json=request, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		assert isinstance(result, object), 'Result is not an object.'
		return result

	def get_inherited_default_blob_server_id(self, access_token, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-blob-server-id')
		response = requests.get(url, params={ 'resource-group-id': resource_group_id }, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		return result

	def get_job(self, access_token, job_id):
		url = join_url(self._api_root, 'get-job')
		response = requests.get(url, params={ 'job-id': job_id }, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		return result

	def abort_job(self, access_token, job_id):
		url = join_url(self._api_root, 'get-job')
		response = requests.post(url, params={ 'job-id': job_id }, headers={ 'Authorization': f'Bearer {access_token}' })
		result = self.process_response(response)
		return result

	def get_ticket(self, access_token, resource_id):
		url = join_url(self._api_root, 'ticket-generator/get-ticket')
		request = {
			'type': 'freeTicket',
			'resources': [resource_id],
			'format': 'base64'
		}
		response = requests.post(url, json=request, headers={ 'Authorization': f'Bearer {access_token}' })
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