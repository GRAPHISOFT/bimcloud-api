import random
import string
import itertools
import os
import requests
from .managerapi import ManagerApi
from .blobserverapi import BlobServerApi
from .url import join_url, parse_url
from .errors import BIMcloudBlobServerError

CHARS = list(itertools.chain(string.ascii_lowercase, string.digits))
PROJECT_ROOT = 'Project Root'
PROJECT_ROOT_ID = 'projectRoot'

class Workflow:
	def __init__(self, manager_url, username, password, client_id):
		self._manager_api = ManagerApi(manager_url)

		self.username = username
		self._password = password
		self.client_id = client_id
		self._session_id = None
		self._user_id = None

		self._root_dir_name = Workflow.to_unique('DEMO_RootDir')
		self._sub_dir_name = Workflow.to_unique('DEMO_SubDir')
		self._root_dir_data = None
		self._sub_dir_data = None
		self._inner_dir_path = None
		self._model_server_urls = {}
		self._blob_server_sessions = {}

	def run(self):
		# WORKFLOW BEGIN
		self.login()
		try:
			self.create_dirs()
			self.upload_files()
			self.locate_download_and_delete_files()
		finally:
			self.logout()
		# WORKFLOW END

	def login(self):
		print(f'Login as {self.username} ...')
		self._userId, self._session_id = self._manager_api.create_session(self.username, self._password, self.client_id)
		print('Logged in.')

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
				self._session_id,
				immediate_parent_dir['id'])

		# Blob Server is a role of a Model Server, basically they are the same thing:
		model_server = self._manager_api.get_resource_by_id(self._session_id, configured_blob_server_id)
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
			CHUNK_SIZE = 1024 * 40 # We use 40Kb but IRL it should be around several megabytes.
			offset = 0
			while offset < len(data):
				# Advice: Manager's session should get kept alive during long upload sessions.
				self._manager_api.ping_session(self._session_id)

				chunk = data[offset:offset + CHUNK_SIZE]
				blob_server_api.put_blob_content_part(blob_server_session_id, upload['id'], chunk, offset=offset)
				offset += CHUNK_SIZE

			blob_server_api.commit_upload(blob_server_session_id, upload['id'])
			blob_server_api.commit_batch_upload(blob_server_session_id, batch['id'])

			print(f'File uploaded as "{blob_server_file_path}".')

		self.run_with_blob_server_session(model_server, do_upload)

	def locate_download_and_delete_files(self):
		self.locate_download_and_delete_files_in(self._root_dir_data)

	def locate_download_and_delete_files_in(self, directory):
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
			content = self._manager_api.get_resources_by_criterion(self._session_id, criterion, options)
			all_content.extend(content)
			if len(content) < limit:
				break
			options['skip'] += limit

		if not all_content:
			print(f'Directory has not content.')
			return

		print(f'Directory has {len(all_content)} resouurces.')

		# Type of directory is 'resourceGroup' in BIMcloud.
		for subdir in filter(lambda i: i['type'] == 'resourceGroup', all_content):
			self.locate_download_and_delete_files_in(subdir)

		# Type of file is 'blob' in BIMcloud.
		for blob in filter(lambda i: i['type'] == 'blob', all_content):
			self.download_and_delete_file(blob)

		# We do this at last, because non-empty directories cannot get deleted (easily).
		self._manager_api.delete_resource_group(self._session_id, directory_id)
		print(f'\nDirectory "{directory_path}" deleted.')

	def download_and_delete_file(self, blob):
		blob_id = blob['id']
		blob_path = blob['$path']

		blob_model_server_id = blob['modelServerId']
		blob_model_server = self._manager_api.get_resource_by_id(self._session_id, blob_model_server_id)

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

		self._manager_api.delete_blob(self._session_id, blob_id)
		print(f'\nBlob "{blob_path}" deleted.')

	def run_with_blob_server_session(self, model_server, fn):
		blob_server_session_id, blob_server_api = self._blob_server_sessions.get(model_server['id'], (None, None))
		if blob_server_session_id is None:
			# There could be Many Model Server urls configured,
			# to be able to accessed from different network locations.
			# We should pick that one that we can access.
			model_server_url = self.find_working_model_server_url(model_server)
			blob_server_api = BlobServerApi(model_server_url)

			# Ticket is an authentication token for Model (Blob) Server.
			ticket = self._manager_api.get_ticket(self._session_id, model_server['id'])

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
		dir_data = self._manager_api.get_resource(self._session_id, by_path=path, try_get=True)
		if dir_data is None or dir_data['type'] != 'resourceGroup':
			idx = path.rindex('/')
			return self.find_immediate_parent_dir(path[0:idx])
		return dir_data

	def get_or_create_dir(self, name, parent=None):
		path_of_dir = name if parent is None else join_url(parent['$path'], name)
		path_of_dir = self.ensure_root(path_of_dir)

		print(f'Getting directory "{path_of_dir}" ...')
		dir_data = self._manager_api.get_resource(self._session_id, by_path=path_of_dir)

		if dir_data is not None:
			print('Directory exists.')
			return dir_data

		print('Directory doesn\'t exist, creating ...')

		dir_id = self._manager_api.create_resource_group(
			self._session_id,
			name,
			parent['id'] if parent is not None else PROJECT_ROOT_ID)

		dir_data = self._manager_api.get_resource(self._session_id, by_id=dir_id)

		dir_path = dir_data['$path']
		assert dir_path == path_of_dir, 'Resource created on a wrong path.'

		print('Directory created.')

		return dir_data

	def logout(self):
		self._manager_api.close_session(self._session_id)
		for server_id in self._blob_server_sessions:
			session_id, api = self._blob_server_sessions[server_id]
			api.close_session(session_id)
		self._blob_server_sessions = {}
		self._session_id = None
		self._model_server_urls = {}

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