import datetime
from email.utils import unquote
import random
import string
import itertools
import os
import tempfile
import requests
import time
import json
from .managerapi import ManagerApi
from .blobserverapi import BlobServerApi
from .url import join_url, parse_url
from .errors import BIMcloudBlobServerError, BIMcloudManagerError
import uuid
from urllib.parse import unquote, urlparse

CHARS = list(itertools.chain(string.ascii_lowercase, string.digits))
PROJECT_ROOT = 'Project Root'
PROJECT_ROOT_ID = 'projectRoot'

class Workflow:
	def __init__(self, manager_url, client_id, un_pw=None, temp_dir=None):
		self._manager_api = ManagerApi(manager_url)

		self.client_id = client_id
		self.username = None
		self._un_pw = un_pw
		self._temp_dir = temp_dir if temp_dir else os.path.join(tempfile.gettempdir(), Workflow.to_unique('bimcloud_temp'))

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
		self.login()
		try:
			self.create_dirs()
			self.upload_files()
			self.rename_file()
			self.move_file()
			self.locate_download_and_delete_files()
			self.create_directory_tree_and_delete_recursively()
			self.find_a_project_snapshot_download_import_then_delete() # This example explains how to handle projects and libraries. Check the comments.
			self.find_a_project_export_import_then_delete() # This example explains how to handle projects and libraries. Check the comments.
			self.create_a_bcp_move_a_project_there_then_move_back() # This example explains how to handle projects, libraries, blobs and folders. Check the comments.
		finally:
			self.logout()
		# WORKFLOW END

	def login(self):
		if self._un_pw is None:
			self.login_sso()
		else:
			print('Logging in with user name and password ...')
			self._auth_context = self._manager_api.get_token_by_password_grant(*self._un_pw, self.client_id)
			self.username = self._manager_api.get_user(self._auth_context, self._auth_context.user_id)['username']
			print('Logged in.')

	def login_sso(self):
		print('Logging in with SSO ...')
		state = uuid.uuid4()
		self._manager_api.open_authorization_page(self.client_id, state)
		time.sleep(1)

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
				immediate_parent_dir['id']
			)

		# Blob Server is a role of a Model Server, basically they are the same thing:
		model_server = self._manager_api.get_resource_by_id(self._auth_context, configured_blob_server_id['result'])
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
		self.wait_for_job_completion(job)

	def download_and_delete_file(self, blob):
		blob_id = blob['id']
		blob_path = blob['$path']

		blob_model_server_id = blob['modelServerId']
		blob_model_server = self._manager_api.get_resource_by_id(self._auth_context, blob_model_server_id)

		def download(blob_server_session_id, blob_server_api):
			print(f'\nDownloading "{blob_path}".')
			response = blob_server_api.get_blob_content(blob_server_session_id, blob_id)
			try:
				first_byte = None
				last_byte = None
				size = 0
				for chunk in response.iter_content(chunk_size=8192):
					if chunk:
						size += len(chunk)
						if not first_byte:
							first_byte = chunk[0]
						last_byte = chunk[-1]
				print(f'Downloaded {size} bytes. First byte: {first_byte}, last byte: {last_byte}.')
			finally:
				response.close()

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

	def find_a_project_snapshot_download_import_then_delete(self):
		# find a project somewhere in the BIMcloud that has a snapshot,
		projects = self._manager_api.get_resources_by_criterion(
			self._auth_context,
			{ '$eq': { 'type': 'project' } },
			{ 'sort-by': '$loweredPath' }
		)

		if not projects:
			print('No projects found, skipping snapshot demo.')
			return

		print(f'Found {len(projects)} projects, picking the one with snapshots ...')

		for project in projects:
			project_snapshots = self._manager_api.get_resource_backups_by_criterion(
				self._auth_context,
				{
					'ids': [project['id']],
					'criterion': {
						'$and': [
							{ '$eq': { '$resourceType': 'project' } }, # to get library backups, use '$resourceType': 'library'
							{ '$eq': { '$formatId': '_server.backup.format.bimproject' } },
							{ '$eq': { '$statusId': '_server.backup.status.done' } },
						]
					}
				},
			)

			if project_snapshots:
				found_project = project
				found_snapshot = project_snapshots[0]
				print(f'Found project "{found_project["name"]}" (id: {found_project["id"]}) with snapshot "{found_snapshot["$name"]}" (id: {found_snapshot["id"]}).')
				self.download_snapshot_import_then_delete(found_project, found_snapshot)
				return

		print('No projects with snapshots found, skipping snapshot demo.')

	def download_snapshot_import_then_delete(self, project, snapshot):
		print(f'Downloading snapshot "{snapshot["$name"]}" of project "{project["name"]}" to "{self._temp_dir}".')
		os.makedirs(self._temp_dir, exist_ok=True)

		fn = Workflow.to_unique(f'{project["name"]}_{snapshot["$name"]}')
		file_path = os.path.join(self._temp_dir, f'{fn}.bimproject')
		response = self._manager_api.download_backup(self._auth_context, snapshot["id"], project["id"])
		try:
			# Save the snapshot to a file using streaming:
			with open(file_path, 'wb') as f:
				for chunk in response.iter_content(chunk_size=8192):
					if chunk:  # Filter out keep-alive chunks
						f.write(chunk)

			print(f'Snapshot saved to "{file_path}".')
			self.restore_snapshot_then_delete(
				project['modelServerId'],
				project['$parentId'],
				project['name'],
				file_path=file_path
			)
		finally:
			response.close()
			os.remove(file_path)
			print(f'Snapshot file "{file_path}" deleted.')

	def restore_snapshot_then_delete(self, model_server_id, parent_id, project_name, file_path):
		model_server = self._manager_api.get_resource_by_id(self._auth_context, model_server_id)
		model_server_url = self.find_working_model_server_url(model_server)
		parent = self._manager_api.get_resource_by_id(self._auth_context, parent_id)
		print(f'Restoring snapshot from "{file_path}" to Model Server "{model_server['name']}" (url: {model_server_url}) under parent directory "{parent['name']}".')

		import_urls = self._manager_api.import_project_get_url(self._auth_context, model_server_id, parent_id) # to import library backups, use import_library_get_url
		import_url = join_url(model_server_url, import_urls['url'])
		print(f'Uploading file string to import url: {import_url}')

		# File uri is a query string parameter (file-uri) of the import_url string. We should parse the url, ad get the file-uri parameter.
		parsed_import_url = urlparse(import_url)

		# parsed_import_url.query is a string, we should parse and process it:
		query_params_dict = {}
		if parsed_import_url.query:
			query_params_dict = dict(param.split('=') for param in parsed_import_url.query.split('&'))
		file_uri = query_params_dict.get('file-uri')
		assert file_uri, 'File URI not found in import URL.'
		# decode file_uri from url encoding:
		file_uri = unquote(file_uri)


		with open(file_path, 'rb') as f:
			# post the file content to the import url:
			response = requests.post(import_url, data=f, headers={'Content-Type': 'application/octet-stream'})
			if not response.ok:
				raise BIMcloudManagerError(f'Failed to upload snapshot file to import url: {response.status_code} - {response.reason}')

		print('File uploaded.')
		self.import_project_and_delete(model_server_id, parent, file_uri, project_name)

	def import_project_and_delete(self, model_server_id, parent, file_uri, project_name):
		new_project_name = Workflow.to_unique(project_name)
		new_project_path = f"{parent['$path']}/{new_project_name}"
		print(f'Importing project "{new_project_path}" from file uri "{file_uri}".')

		job = self._manager_api.import_project_as_new(
			self._auth_context,
			model_server_id,
			parent['id'],
			file_uri,
			new_project_name
		) # to import library backups, use import_library_as_new

		self.wait_for_job_completion(job)

		imported_project = self._manager_api.get_resource(self._auth_context, by_path=new_project_path)

		print(f'"{imported_project["$path"]}" imported successfully, id: {imported_project["id"]}.')

		self.delete_project(imported_project)

	def delete_project(self, project):
		print(f'Deleting project "{project['$path']}".')
		self._manager_api.delete_project(self._auth_context, project['id']) # to delete library backups, use delete_library
		print('Project deleted.')

	def find_a_project_export_import_then_delete(self):
		# find a project somewhere in the BIMcloud.
		projects = self._manager_api.get_resources_by_criterion(
			self._auth_context,
			{ '$eq': { 'type': 'project' } },
			{ 'sort-by': '$loweredPath', 'limit': 1 },
		)

		if not projects:
			print('No projects found, skipping snapshot demo.')
			return

		assert len(projects) == 1

		project = projects[0]
		print(f'Found project "{project["name"]}" (id: {project["id"]}).')

		self.export_project_then_import_then_delete(project)

	def export_project_then_import_then_delete(self, project):
		job = self._manager_api.export_project(
			self._auth_context,
			project['id'],
		) # export_library can be used in case of libraries

		job = self.wait_for_job_completion(job)
		snapshot_url = next((prop['value'] for prop in job['properties'] if prop['name'] == 'absoluteUrl'), None)

		if not snapshot_url:
			raise KeyError('absoluteUrl not found in job properties')

		print(f'Downloading snapshot "{snapshot_url}" of project "{project["name"]}" to "{self._temp_dir}".')
		os.makedirs(self._temp_dir, exist_ok=True)

		fn = Workflow.to_unique(f'{project["name"]}_imported')
		file_path = os.path.join(self._temp_dir, f'{fn}.bimproject')
		response = requests.get(
			snapshot_url,
			False,
			verify=False, # Disable SSL verification for demo purposes, not recommended in production!
			stream=True
		)
		try:
			# Save the snapshot to a file using streaming:
			with open(file_path, 'wb') as f:
				for chunk in response.iter_content(chunk_size=8192):
					if chunk:  # Filter out keep-alive chunks
						f.write(chunk)

			print(f'Snapshot saved to "{file_path}".')
			self.restore_snapshot_then_delete(
				project['modelServerId'],
				project['$parentId'],
				project['name'],
				file_path=file_path
			)
		finally:
			response.close()
			os.remove(file_path)
			print(f'Snapshot file "{file_path}" deleted.')

	def create_a_bcp_move_a_project_there_then_move_back(self):
		# Note you can use any type of resource in this example, not just projects (eg. update_library_parent instead of update_project_parent).

		# find a project somewhere in the BIMcloud.
		projects = self._manager_api.get_resources_by_criterion(
			self._auth_context,
			{ '$eq': { 'type': 'project' } },
			{ 'sort-by': '$loweredPath', 'limit': 1 },
		)

		if not projects:
			print('No projects found, skipping snapshot demo.')
			return

		assert len(projects) == 1

		project = projects[0]
		print(f'Found project "{project["name"]}" (id: {project["id"]}). Moving under project root.')

		original_parent_id = project['$parentId']

		bcp_name = Workflow.to_unique('DEMO_BCP')
		bcp_folder = self.get_or_create_dir(bcp_name)

		print(f'BCP folder "{bcp_folder["$path"]}" created. Promoting it to a BCP.')

		self._manager_api.insert_bimcloudproject(self._auth_context, bcp_folder["id"])

		print(f'BCP "{bcp_folder["$path"]}" created. Moving project "{project["name"]}" there.')

		self._manager_api.update_project_parent(
			self._auth_context,
			project['id'],
			{
				'parentPath': bcp_folder['$path']
			}
		)

		print(f'Project "{project["name"]}" moved to BCP "{bcp_folder["$path"]}".')
		print('Moving project back to previous location.')

		self._manager_api.update_project_parent(
			self._auth_context,
			project['id'],
			{
				'parentId': original_parent_id
			}
		)

		print(f'Project "{project["name"]}" moved back to its original location.')

		print('Deleting BCP folder.')
		self._manager_api.delete_resource_group(self._auth_context, bcp_folder['id'])

		print(f'BCP folder "{bcp_folder["$path"]}" deleted.')

	def wait_for_job_completion(self, job):
		print(f'Job has been started. Id: {job["id"]}, type: {job["jobType"]}.')
		print('\nWaiting to job get completed.')
		while job['status'] != 'completed' and job['status'] != 'failed':
			print(f'Job stauts is {job["status"]}, polling ...')
			time.sleep(1)
			job = self._manager_api.get_job(self._auth_context, job['id'])

		if job['status'] == 'completed':
			print('Job has been completed successfully.')
			print(f'Result code: {job["resultCode"]}')
			print('Progress:')
			print(json.dumps(job['progress'], sort_keys=False, indent=4))
			return job
		else:
			assert job['status'] == 'failed'
			raise BIMcloudManagerError(f'Job has been failed. Id: {job["id"]}, type: {job["jobType"]}.')

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
