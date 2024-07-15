import datetime
import random
import string
import itertools
import os
import requests
import time
import json
from .managerapi import ManagerApi
from .blobserverapi import BlobServerApi
from .url import join_url, parse_url
from .errors import BIMcloudBlobServerError, BIMcloudManagerError
import uuid

CHARS = list(itertools.chain(string.ascii_lowercase, string.digits))
PROJECT_ROOT = 'Project Root'
PROJECT_ROOT_ID = 'projectRoot'

class Workflow:
	def __init__(self, manager_url, client_id, username=None, password=None):
		self._manager_api = ManagerApi(manager_url)
		self._blobserv_api = BlobServerApi(manager_url)
		self.client_id = client_id

		self.username = username
		self.password = password
		self._auth_context = None

		self._root_dir_name = Workflow.to_unique('DEMO_RootDir')
		self._sub_dir_name = Workflow.to_unique('DEMO_SubDir')
		self._root_dir_data = None
		self._sub_dir_data = None
		self._inner_dir_path = None
		self._model_server_urls = {}
		self._blob_server_sessions = {}

		# Changeset polling starts on revision 0
		self._next_revision_for_sync = 0

	def run(self):
		# WORKFLOW BEGIN
		# self.login_sso()
		self.login_pwd()
		try:
			# self.create_dirs()
			# self.upload_files()
			# self.rename_file()
			# self.move_file()
			# self.locate_download_and_delete_files()
			# self.create_directory_tree_and_delete_recursively()
			# test = dir(ManagerApi)
			test = self._manager_api.get_local_model_servers_data(self._auth_context)
			# print(json.dumps(test, indent = 4))
			print(test)
			# self._manager_api.get_user(self._auth_context, self._auth_context.user_id )
		finally:
			self.logout()
		# WORKFLOW END

	def login_pwd(self):
		print('Logging in ...')
		self._auth_context = self._manager_api.get_token_by_password_grant(self.username, self.password, self.client_id)

		if self._auth_context is None:
			print('Login failed')
			quit(1)
		# elif self._auth_context._access_token and self._auth_context._refresh_token:
		# 	print(f'Received token type is "{self._auth_context.token_type}"')
		# 	print(f'Access token is going to expire at {Workflow.convert_timestamp(self._auth_context.access_token_exp)}')
		# 	print('Logged in.')

	def login_sso(self):
		print('Logging in ...')
		state = uuid.uuid4()
		self._manager_api.open_authorization_page(self.client_id, state)
		time.sleep(0.2)

		authorization_code = None
		for i in range(300):
			result = self._manager_api.get_authorization_code_by_state(state)
			print (result)
			if result[0] == 'succeeded':
				authorization_code = result[1]
				break
			elif result[0] == 'pending':
				print('Waiting for login ...')
				time.sleep(1)

		if authorization_code is None:
			print('Login failed')
			quit(1)

		print('Exchanging authorization code for access & refresh token')
		self._auth_context = self._manager_api.get_token_by_authorization_code_grant(authorization_code, self.client_id)
		print(f'Received token type is "{self._auth_context.token_type}"')
		print(f'Access token is going to expire at {Workflow.convert_timestamp(self._auth_context.access_token_exp)}')
		print('Logged in.')

		self.username = self._manager_api.get_user(self._auth_context, self._auth_context.user_id)['username']

	def create_dirs(self):
		print('Creating directories ...')
		self._root_dir_data = self.get_or_create_dir(self._root_dir_name)
		self._sub_dir_data = self.get_or_create_dir(self._sub_dir_name, self._root_dir_data)
		print('Directories created.')

	def upload_files(self):
		print('Uploading files ...')

		self.upload_file(self._root_dir_data['$path'], 'pic1.jpg')
		self.upload_file(self._sub_dir_data['$path'], 'text1.txt')
		self.upload_file(self._sub_dir_data['$path'], 'text2.txt')

		# Addign a new version of an already existsing file.
		# You can find file versions on Manager's UI.
		self.upload_file(self._sub_dir_data['$path'], 'text2.1.txt', 'text2.txt')

		# We can even upload files to non-existsing paths,
		# required directories will get createad.
		self._inner_dir_path = join_url(self._sub_dir_data['$path'], self.to_unique('foo'), self.to_unique('bar'))
		self.upload_file(self._inner_dir_path, 'pic2.jpg')

		self.wait_for_blob_changes()

		print('\nFiles uploaded.')

	def upload_file(self, path, name, alias=None):
		if not alias:
			alias = name
		file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'blobs', name))
		description = f'\nUploading file "{file_path}" to "{path}/{alias}" ...'
		print(description)

		data = None
		with open(file_path, 'rb') as f: data = f.read()

		# To know to which File Server we should upload the file,
		# we should get the setting.
		immediate_parent_dir = self.find_immediate_parent_dir(path)
		immediate_parent_path = immediate_parent_dir['$path']
		print(f'Immediate existing parent directory: "{immediate_parent_path}".')

		configured_blob_server_id = \
			self._manager_api.get_inherited_default_blob_server_id(
				self._auth_context,
				immediate_parent_dir['id'])

		# Blob Server is a role of a Model Server, basically they are the same thing:
		model_server = self._manager_api.get_resource_by_id(self._auth_context, configured_blob_server_id)
		model_server_name = model_server['name']
		print(f'Configured host Blob Server: "{ model_server_name }".')

		def do_upload(blob_server_session_id: str, blob_server_api: BlobServerApi):
			print('Uploading data ...')

			# For more efficient uploads, we could use one batch for many upload operations,
			# and commit them together.
			# But for the sake of simplicity, we open a batch for every upload for now.
			batch = blob_server_api.begin_batch_upload(blob_server_session_id, description)

			# We should extract the manager side mandatory "Project Root" prefix:
			blob_server_file_path = self.create_blob_server_path(path, alias)

			upload = blob_server_api.begin_upload(blob_server_session_id, blob_server_file_path, batch['namespace-name'])

			# It is advised to upload large content in chunks.
			CHUNK_SIZE = 1024 * 40 # NOTE: We use 40Kb for the DEMO but in real life it should be around several megabytes!
			offset = 0
			while offset < len(data):
				chunk = data[offset:offset + CHUNK_SIZE]
				blob_server_api.put_blob_content_part(blob_server_session_id, upload['id'], chunk, offset=offset)
				offset += CHUNK_SIZE

			blob_server_api.commit_upload(blob_server_session_id, upload['id'])
			blob_server_api.commit_batch_upload(blob_server_session_id, batch['id'])

			print(f'File uploaded as "{blob_server_file_path}".')

		self.run_with_blob_server_session(model_server, do_upload)

	def rename_file(self):
		print('\nRenaming a file ...')

		text1_blob_path = join_url(self._sub_dir_data['$path'], 'text1.txt')
		text1_blob = self._manager_api.get_resource(self._auth_context, text1_blob_path)

		update_body = {
			# Update body should contains the identifier.
			'id': text1_blob['id'],
			# And to-be-updated properties with their new values.
			# Please note properties with names starting with '$' cannot get updated from client side, they are read only. (Like $parentId, $path, etc.)
			'name': 'text1_rename.txt'
		}

		self._manager_api.update_blob(self._auth_context, update_body)

		self.wait_for_blob_changes()

	def move_file(self):
		print('\nMoving a file (updating parent path) ...')

		text2_blob_path = join_url(self._sub_dir_data['$path'], 'text2.txt')
		text2_blob = self._manager_api.get_resource(self._auth_context, text2_blob_path)

		body = {
			# aka.: move file to its parent's parent directory.
			'parentPath': self._root_dir_data['$path']
		}

		self._manager_api.update_blob_parent(self._auth_context, text2_blob['id'], body)

		self.wait_for_blob_changes()

	def locate_download_and_delete_files(self):
		self.locate_download_and_delete_files_in(self._root_dir_data, True)

	def locate_download_and_delete_files_in(self, directory, get_changes=False):
		directory_id = directory['id']
		directory_path = directory['$path']

		print(f'\nGetting content of directory "{directory_path}".')

		# To look up content of a directory, we get all resources
		# which have parents set as the directory.

		criterion = { '$eq': { '$parentId': directory_id } }

		# All query APIs have default result limit of 1000 items,
		# so you should get contents of directories by using pagination.
		limit = 100 # Keep it reasonably small.
		options = {
			'sort-by': 'name',
			'skip': 0,
			'limit': limit
		}
		all_content = []
		while True:
			content = self._manager_api.get_resources_by_criterion(self._auth_context, criterion, options)
			all_content.extend(content)
			if len(content) < limit:
				break
			options['skip'] += limit

		if not all_content:
			print('Directory has no content.')
			return

		print(f'Directory has {len(all_content)} resources.')

		# Type of directory is 'resourceGroup' in BIMcloud.
		for subdir in filter(lambda i: i['type'] == 'resourceGroup', all_content):
			self.locate_download_and_delete_files_in(subdir)

		# Type of file is 'blob' in BIMcloud.
		for blob in filter(lambda i: i['type'] == 'blob', all_content):
			self.download_and_delete_file(blob)

		if get_changes:
			self.wait_for_blob_changes()

		# We do this at last, because non-empty directories cannot get deleted (easily).
		self._manager_api.delete_resource_group(self._auth_context, directory_id)
		print(f'\nDirectory "{directory_path}" deleted.')

	def create_directory_tree_and_delete_recursively(self):
		print('Creating and deleting a directory subtree.')

		# Creating example directory tree structure:
		# example_root
		# L example_sub1
		#  L example_sub1_sub1
		#  L example_sub1_sub2
		# L example_sub2
		#  L example_sub2_sub1
		#  L example_sub2_sub2
		example_root_dir = self.get_or_create_dir(Workflow.to_unique('example_root'))
		example_sub1_dir = self.get_or_create_dir(Workflow.to_unique('example_sub1'), example_root_dir)
		example_sub2_dir = self.get_or_create_dir(Workflow.to_unique('example_sub2'), example_root_dir)
		self.get_or_create_dir(Workflow.to_unique('example_sub1_sub1'), example_sub1_dir)
		self.get_or_create_dir(Workflow.to_unique('example_sub1_sub2'), example_sub1_dir)
		self.get_or_create_dir(Workflow.to_unique('example_sub2_sub1'), example_sub2_dir)
		self.get_or_create_dir(Workflow.to_unique('example_sub2_sub2'), example_sub2_dir)

		print(f'Example directory subtree created in {example_root_dir["name"]}.')

		# We can delete directorys with their entire content recursively by using delete-resources-by-id-list API.
		# The API is asynchronous which means the directory won't get deleted as soon as the API call get finished.
		# The result of the API is a job that we can poll to get result of the ongoing delete operation.

		print(f'\nStartig job to delete {example_root_dir["name"]} recusively.')

		job = self._manager_api.delete_resources_by_id_list(self._auth_context, [example_root_dir['id']])

		print(f'Job has been started. Id: {job["id"]}, type: {job["jobType"]}.')
		print('\nWaiting to job get completed.')
		while job['status'] != 'completed' and job['status'] != 'failed':
			print(f'Job stauts is {job["status"]}, polling ...')
			time.sleep(0.1)
			job = self._manager_api.get_job(self._auth_context, job['id'])

		if job['status'] == 'completed':
			print('Job has been completed successfully.')
			print(f'Result code: {job["resultCode"]}')
			print('Progress:')
			print(json.dumps(job['progress'], sort_keys=False, indent=4))
		else:
			assert job['status'] == 'failed'
			print(f'Job has been falied. Erro code: {job["resultCode"]}, error message: {job["result"]}.')

	def download_and_delete_file(self, blob):
		blob_id = blob['id']
		blob_path = blob['$path']

		blob_model_server_id = blob['modelServerId']
		blob_model_server = self._manager_api.get_resource_by_id(self._auth_context, blob_model_server_id)

		def download(blob_server_session_id, blob_server_api):
			print(f'\nDownloading "{blob_path}".')
			stream = blob_server_api.get_blob_content(blob_server_session_id, blob_id)
			first_byte = None
			last_byte = None
			size = 0
			for chunk in stream.iter_content(chunk_size=8192):
				if chunk:
					size += len(chunk)
					if not first_byte:
						first_byte = chunk[0]
					last_byte = chunk[-1]
			print(f'Downloaded {size} bytes. First byte: {first_byte}, last byte: {last_byte}.')

		self.run_with_blob_server_session(blob_model_server, download)

		self._manager_api.delete_blob(self._auth_context, blob_id)
		print(f'\nBlob "{blob_path}" deleted.')

	def run_with_blob_server_session(self, model_server, fn):
		blob_server_session_id, blob_server_api = self._blob_server_sessions.get(model_server['id'], (None, None))
		if blob_server_session_id is None:
			# There could be Many Model Server urls configured,
			# to be able to accessed from different network locations.
			# We should pick that one that we can access.
			model_server_url = self.find_working_model_server_url(model_server)
			print(model_server_url)
			blob_server_api = BlobServerApi(model_server_url)

			# Ticket is an authentication token for Model (Blob) Server.
			ticket = self._manager_api.get_ticket(self._auth_context, model_server['id'])

			blob_server_session_id = blob_server_api.create_session(self.username, ticket)

			self._blob_server_sessions[model_server['id']] = (blob_server_session_id, blob_server_api)

		try:
			return fn(blob_server_session_id, blob_server_api)
		except BIMcloudBlobServerError as err:
			if err.code == 4 or err.code == 11:
				# Session or ticket expired, drop:
				del self._blob_server_sessions[model_server['id']]
				# Retry:
				return self.run_with_blob_server_session(model_server, fn)
			raise err

	def find_working_model_server_url(self, model_server):
		# We should cache this, because it's static and takes too long to determine:
		result_url = self._model_server_urls.get(model_server['id'])
		if result_url is not None:
			return result_url

		possible_urls = model_server['connectionUrls']
		assert isinstance(possible_urls, list), '"possible_urls" is not a list.'
		parsed_manager_url = parse_url(self._manager_api.manager_url)
		manager_hostname = parsed_manager_url.hostname
		manager_protocol = parsed_manager_url.scheme + ':'

		# Order is important here, urls on top are most likely accessible.
		for url in possible_urls:
			url = url.replace('$protocol', manager_protocol)
			url = url.replace('$hostname', manager_hostname)
			try:
				response = requests.get(join_url(url, 'application-server-service/get-runtime-id'))
				if response.ok:
					self._model_server_urls[model_server['id']] = url
					return url
			except:
				pass
		model_server_name = model_server['name']
		raise RuntimeError(f'Model Server "{model_server_name}" is unreachable.')

	def find_immediate_parent_dir(self, path):
		# We should find the immediate existing (parent) directory of an arbitrary path.
		dir_data = self._manager_api.get_resource(self._auth_context, by_path=path, try_get=True)
		if dir_data is None or dir_data['type'] != 'resourceGroup':
			idx = path.rindex('/')
			return self.find_immediate_parent_dir(path[0:idx])
		return dir_data

	def get_or_create_dir(self, name, parent=None):
		path_of_dir = name if parent is None else join_url(parent['$path'], name)
		path_of_dir = self.ensure_root(path_of_dir)

		print(f'Getting directory "{path_of_dir}" ...')
		dir_data = self._manager_api.get_resource(self._auth_context, by_path=path_of_dir)

		if dir_data is not None:
			print('Directory exists.')
			return dir_data

		print('Directory doesn\'t exist, creating ...')

		dir_id = self._manager_api.create_resource_group(
			self._auth_context,
			name,
			parent['id'] if parent is not None else PROJECT_ROOT_ID)

		dir_data = self._manager_api.get_resource(self._auth_context, by_id=dir_id)

		dir_path = dir_data['$path']
		assert dir_path == path_of_dir, 'Resource created on a wrong path.'

		print('Directory created.')

		return dir_data

	def logout(self):
		# Since access tokens are decentralized, manager API is lack of logout methods
		for server_id in self._blob_server_sessions:
			session_id, api = self._blob_server_sessions[server_id]
			api.close_session(session_id)
		self._blob_server_sessions = {}
		self._auth_context = None
		self._model_server_urls = {}

	def wait_for_blob_changes(self):
		# It migth take a couple of seconds until the next changeset appears.
		for i in range(10):
			if self.get_blob_changes(str(i + 1)):
				break
			time.sleep(3)

	def get_blob_changes(self, attempt):
		# Blob Server side changes are accessible for helping synchronization scenarios.
		# We support a simple polling mechanism for that, by utilizing the get-blob-changes-for-sync API.
		# Changesets are separated by revisions, and synchronization always start at revision 0.
		# Revision 0 is a special case, it gives all content in the given directory in its result's "created" array field.
		# After revision 0 the next set of changes are are accessible by using the last knonw changeset's "endRevision" value in the request's "fromRevison" parameter.
		curr_revision = self._next_revision_for_sync
		try:
			path = self._root_dir_data['$path']
			print(f'\nAttempt #{attempt}: Getting changes after revision {curr_revision} from: "{path}".\n')

			blob_changes = self._manager_api.get_blob_changes_for_sync(self._auth_context, path, None, curr_revision)

			print(json.dumps(blob_changes, sort_keys=False, indent=4))

			self._next_revision_for_sync = blob_changes['endRevision']
		except BIMcloudManagerError as err:
			if err.code == 9:
				# Error code 9 means Revision Obsoleted Error.
				# This happen when the underlying content database has been replaced to another one under the hood,
				# for example after restoring backups.
				# When this happens, synchronization flow should reset, and should get started from revision 0.
				# The first response from revision zero will contain the whole content of the of the directory in the new database in the "created" array field of the API result.
				# The client should use this as a basis of a new synchronization cycle, and should reinitialize its content according the content of the "created" array.
				self._next_revision_for_sync = 0
				return self.get_blob_changes(attempt + ':RESET')
			else:
				raise
		return self._next_revision_for_sync != curr_revision

	@staticmethod
	def create_blob_server_path(manager_dir_path, file_name):
		return join_url(manager_dir_path[len(PROJECT_ROOT):], file_name)

	@staticmethod
	def ensure_root(path):
		# resource paths under Project Root starts with "Project Root".
		return path if path.startswith(PROJECT_ROOT) else join_url(PROJECT_ROOT, path)

	@staticmethod
	def to_unique(name):
		return f'{name}_{random.choice(CHARS)}{random.choice(CHARS)}{random.choice(CHARS)}{random.choice(CHARS)}'

	@staticmethod
	def convert_timestamp(timestamp):
		return datetime.datetime.fromtimestamp(timestamp).strftime("%B %d, %Y %I:%M:%S")
