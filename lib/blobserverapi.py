import requests
from .errors import raise_bimcloud_blob_server_error, BIMcloudBlobServerError, HttpError
from .url import is_url, join_url

class BlobServerApi:
	def __init__(self, server_url):
		if not is_url(server_url):
			raise ValueError('Server url is invalid.')

		self.server_url = server_url

	def create_session(self, username, ticket):
		request = {
			'data-content-type': 'application/vnd.graphisoft.teamwork.session-service-1.0.authentication-request-1.0+json',
			'data': {
				'username': username,
				'ticket': ticket
			}
		}
		url = join_url(self.server_url, 'session-service/1.0/create-session')
		response = requests.post(url, json=request, headers={ 'content-type': request['data-content-type'] })
		result = self.process_response(response)
		return result['data']['id']

	def close_session(self, session_id):
		url = join_url(self.server_url, 'session-service/1.0/close-session')
		response = requests.post(url, params={ 'session-id': session_id })
		self.process_response(response)

	def begin_batch_upload(self, session_id, description):
		url = join_url(self.server_url, '/blob-store-service/1.0/begin-batch-upload')
		response = requests.post(url,
			params={
				'session-id': session_id,
				'description': description
			})
		self.process_response(response)
		result = self.process_response(response)
		return result['data']

	def commit_batch_upload(self, session_id, batch_id, conflict_behavior='overwrite'):
		url = join_url(self.server_url, '/blob-store-service/1.0/commit-batch-upload')
		response = requests.post(url,
			params={
				'session-id': session_id,
				'batch-upload-session-id': batch_id,
				'conflict-behavior': conflict_behavior
			})
		self.process_response(response)
		result = self.process_response(response)
		return result['data']

	def begin_upload(self, session_id, path, namespace_name):
		url = join_url(self.server_url, '/blob-store-service/1.0/begin-upload')
		response = requests.post(url,
			params={
				'session-id': session_id,
				'blob-name': path,
				'namespace-name': namespace_name
			})
		self.process_response(response)
		result = self.process_response(response)
		return result['data']

	def commit_upload(self, session_id, upload_id):
		url = join_url(self.server_url, '/blob-store-service/1.0/commit-upload')
		response = requests.post(url,
			params={
				'session-id': session_id,
				'upload-session-id': upload_id
			})
		self.process_response(response)
		result = self.process_response(response)
		return result['data']

	def put_blob_content_part(self, session_id, upload_id, data, offset=None):
		url = join_url(self.server_url, '/blob-store-service/1.0/put-blob-content-part')
		response = requests.post(url,
			params={
				'session-id': session_id,
				'upload-session-id': upload_id,
				'offset': offset if offset else 0,
				'length': len(data)
			},
			data=data)
		self.process_response(response)
		result = self.process_response(response)
		return result['data']

	def get_blob_content(self, session_id, blob_id):
		url = join_url(self.server_url, '/blob-store-service/1.0/get-blob-content')
		response = requests.get(url,
			params={
				'session-id': session_id,
				'blob-id': blob_id
			},
			stream=True)
		self.process_response(response, json=False)
		return response

	@staticmethod
	def process_response(response, json=True):
		# ok, status_code, reason, 430: error-code, error-message
		has_content = response.content is not None and len(response.content)
		try:
			if response.ok:
				if has_content:
					return response.json() if json else response
				else:
					return None
			if response.status_code == 401 or response.status_code == 430:
				# 430: BIMcloud Error
				assert has_content, 'BIMcloud error should has contet.'
				raise_bimcloud_blob_server_error(response.json())
		except BIMcloudBlobServerError as err:
			raise err
		except:
			pass # Model Server gives 200 for invalid paths for legacy reasons
		raise HttpError(response)