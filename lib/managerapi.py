import requests
from .errors import raise_bimcloud_manager_error, HttpError
from .url import is_url, join_url

class ManagerApiRequestContext:
	def __init__(self, user_id, access_token, refresh_token, access_token_exp, refresh_token_exp, token_type, client_id):
		self.user_id = user_id
		self._access_token = access_token
		self._refresh_token = refresh_token
		self.access_token_exp = access_token_exp
		self.refresh_token_exp = refresh_token_exp
		self.token_type = token_type
		self.client_id = client_id

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
		return ManagerApiRequestContext(result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['refresh_token_exp'], result['token_type'], client_id)

	def get_token_by_refresh_token_grant(self, refresh_token, client_id):
		request = {
			'grant_type': 'refresh_token',
			'refresh_token': refresh_token,
			'client_id': client_id
		}
		url = join_url(self._api_root, 'oauth2', 'token')
		response = requests.post(url, data=request, headers={ 'Content-Type': 'application/x-www-form-urlencoded' })
		result = self.process_response(response)
		return ManagerApiRequestContext(result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['refresh_token_exp'], result['token_type'], client_id)

	def get_resource(self, auth_context, by_path=None, by_id=None, try_get=False):
		if by_id is not None:
			return self.get_resource_by_id(auth_context, by_id)

		criterion = None
		if by_path is not None:
			criterion = { '$eq': { '$path': by_path } }

		try:
			return self.get_resource_by_criterion(auth_context, criterion)
		except Exception as err:
			if try_get:
				return None
			raise err

	def get_resource_by_id(self, auth_context, resource_id):
		if resource_id is None:
			raise ValueError('"resource_id"" expected.')

		url = join_url(self._api_root, 'get-resource')
		result = self.refresh_on_timeout(requests.get, auth_context, url, params={ 'resource-id': resource_id })
		return result

	def get_resources_by_criterion(self, auth_context, criterion, options=None):
		if criterion is None:
			raise ValueError('"criterion"" expected.')

		url = join_url(self._api_root, 'get-resources-by-criterion')
		params = {}
		if isinstance(options, dict):
			for key in options:
				params[key] = options[key]

		result = self.refresh_on_timeout(requests.post, auth_context, url, params=params, json=criterion)
		assert isinstance(result, list), 'Result is not a list.'
		return result

	def get_resource_by_criterion(self, auth_context, criterion, options=None):
		result = self.get_resources_by_criterion(auth_context, criterion, options)
		return result[0] if result else None

	def create_resource_group(self, auth_context, name, parent_id=None):
		url = join_url(self._api_root, 'insert-resource-group')
		directory = {
			'name': name,
			'type': 'resourceGroup'
		}
		result = self.refresh_on_timeout(requests.post, auth_context, url, params={ 'parent-id': parent_id }, json=directory)
		assert isinstance(result, str), 'Result is not a string.'
		return result

	def delete_resource_group(self, auth_context, directory_id):
		url = join_url(self._api_root, 'delete-resource-group')
		result = self.refresh_on_timeout(requests.delete, auth_context, url, params={ 'resource-id': directory_id })
		return result

	def delete_resources_by_id_list(self, auth_context, ids):
		url = join_url(self._api_root, 'delete-resources-by-id-list')
		result = self.refresh_on_timeout(requests.post, auth_context, url, json={ 'ids': ids })
		return result

	def delete_blob(self, auth_context, blob_id):
		url = join_url(self._api_root, 'delete-blob')
		self.refresh_on_timeout(requests.delete, auth_context, url, params={'resource-id': blob_id })

	def update_blob(self, auth_context, blob):
		url = join_url(self._api_root, 'update-blob')
		self.refresh_on_timeout(requests.put, auth_context, url, json=blob)

	def update_blob_parent(self, auth_context, blob_id, body):
		url = join_url(self._api_root, 'update-blob-parent')
		self.refresh_on_timeout(requests.post, auth_context, url, params={ 'blob-id': blob_id }, json=body)

	def get_blob_changes_for_sync(self, auth_context, path, resource_group_id, from_revision):
		url = join_url(self._api_root, 'get-blob-changes-for-sync')
		request = {
 			'path': path,
			'resourceGroupId': resource_group_id,
			'fromRevision': from_revision
		}
		result = self.refresh_on_timeout(requests.post, auth_context, url, json=request)
		assert isinstance(result, object), 'Result is not an object.'
		return result

	def get_inherited_default_blob_server_id(self, auth_context, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-blob-server-id')
		result = self.refresh_on_timeout(requests.get, auth_context, url, params={ 'resource-group-id': resource_group_id })
		return result

	def get_job(self, auth_context, job_id):
		url = join_url(self._api_root, 'get-job')
		result = self.refresh_on_timeout(requests.get, auth_context, url, params={ 'job-id': job_id })
		return result

	def abort_job(self, auth_context, job_id):
		url = join_url(self._api_root, 'get-job')
		result = self.refresh_on_timeout(requests.post, auth_context, url, params={ 'job-id': job_id })
		return result

	def get_ticket(self, auth_context, resource_id):
		url = join_url(self._api_root, 'ticket-generator/get-ticket')
		request = {
			'type': 'freeTicket',
			'resources': [resource_id],
			'format': 'base64'
		}
		result = self.refresh_on_timeout(requests.post, auth_context, url, False, json=request)
		assert isinstance(result, bytes), 'Result is not a bytes.'
		result = result.decode('utf-8')
		return result

	def refresh_on_timeout(self, req, auth_context, url, responseJson=True, **kwargs):
		try:
			response = req(url, **kwargs, headers={ 'Authorization': f'Bearer {auth_context._access_token}' })
			return self.process_response(response, json=responseJson)
		except HttpError as e:
			if e.status_code == 401:
				errorJson = e.response.json()
				if 'error' in errorJson and errorJson['error'] == 'invalid_token':
					result = self.get_token_by_refresh_token_grant(auth_context._refresh_token, auth_context.client_id)
					auth_context._access_token = result._access_token
					auth_context._refresh_token = result._refresh_token
					response = req(url, headers={ 'Authorization': f'Bearer {auth_context._access_token}' }, **kwargs)
					return self.process_response(response, json=responseJson)
			raise e

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