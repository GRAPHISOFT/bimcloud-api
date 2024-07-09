import requests
import webbrowser
import tkinter as tk
from tkinter import filedialog

from .blobserverapi import BlobServerApi
from .errors import raise_bimcloud_manager_error, HttpError
from .url import is_url, join_url, add_params

class ManagerApiRequestContext:
	def __init__(self, user_id, access_token, refresh_token, access_token_exp, token_type, client_id):
		self.user_id = user_id
		self._access_token = access_token
		self._refresh_token = refresh_token
		self.access_token_exp = access_token_exp
		self.token_type = token_type
		self.client_id = client_id

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

	def open_authorization_page(self, client_id, state):
		url = add_params(join_url(self._api_root, 'oauth2', 'authorize'), { 'client_id': client_id, 'state': state })
		webbrowser.open(url, new=0, autoraise=0)

	def get_authorization_code_by_state(self, state):
		url = join_url(self._api_root, 'oauth2', 'get-authorization-code-by-state')
		response = requests.get(url, params={ 'state': state })
		result = self.process_response(response)
		return result['status'], result['code']

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
		return ManagerApiRequestContext(result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['token_type'], client_id)

	def get_token_by_refresh_token_grant(self, refresh_token, client_id):
		request = {
			'grant_type': 'refresh_token',
			'refresh_token': refresh_token,
			'client_id': client_id
		}
		url = join_url(self._api_root, 'oauth2', 'token')
		response = requests.post(url, data=request, headers={ 'Content-Type': 'application/x-www-form-urlencoded' })
		result = self.process_response(response)
		return ManagerApiRequestContext(result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['token_type'], client_id)

	def get_token_by_authorization_code_grant(self, authorization_code, client_id):
		request = {
			'grant_type': 'authorization_code',
			'code': authorization_code,
			'client_id': client_id
		}
		url = join_url(self._api_root, 'oauth2', 'token')
		response = requests.post(url, data=request, headers={ 'Content-Type': 'application/x-www-form-urlencoded' })
		result = self.process_response(response)
		return ManagerApiRequestContext(result['user_id'], result['access_token'], result['refresh_token'], result['access_token_exp'], result['token_type'], client_id)

	# 	get-backups-with-unique-resource
	# 	get-backups-with-unique-resource-by-criterion

	def get_ping(self, auth_context):
		url = join_url(self.manager_url, 'ping')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_items_by_criterion(self, auth_context, scope=None, criterion=None, options=None):
		url = join_url(self._api_root, 'get-' + scope + '-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={})
		return result

	def get_inherited_blob_revision_retention_policy(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-inherited-blob-revision-retention-policy')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-id': resource_id})
		return result

	def get_inherited_resource_backup_schedulers(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-inherited-resource-backup-schedulers')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-id': resource_id})
		return result

	def get_lazy_list_position_by_criterion(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-lazy-list-position-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-id': resource_id, 'sort-by': 'id', 'sort-direction': 'asc'})
		return result

	def get_edition_status(self, auth_context):
		url = join_url(self._api_root, 'get-edition-status')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_network_info(self, auth_context):
		url = join_url(self._api_root, 'get-network-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_server_info(self, auth_context):
		url = join_url(self.manager_url, 'get-server-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_webui_config(self, auth_context):
		url = join_url(self.manager_url, 'get-webui-config')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_library_root_path(self, auth_context):
		url = join_url(self._api_root, 'get-library-root-path')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_floating_features(self, auth_context):
		url = join_url(self._api_root, 'get-floating-features')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_server_public_key(self, auth_context):
		url = join_url(self._api_root, 'get-server-public-key')
		response = requests.get(url, params={})
		result = self.process_response(response, json=False)
		return result

	def get_company_logo(self, auth_context):
		url = join_url(self._api_root, 'get-company-logo')
		response = requests.get(url, params={})
		result = self.process_response(response, json=False)
		return result

	def get_locale_config(self, auth_context):
		url = join_url(self._api_root, 'get-locale-config')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_locale_by_id(self, auth_context, lang_id):
		url = join_url(self._api_root, 'get-locale-by-id')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'lang-id': lang_id})
		return result

	def get_announcement(self, auth_context):
		url = join_url(self._api_root, 'get-announcement')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_effective_permissions_by_criterion(self, auth_context, resource_type, criterion=None):
		#resource-type: authorizables, privileges, resources
		url = join_url(self._api_root, 'get-effective-permissions-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-type': resource_type}, json=criterion)
		return result	

	def get_project_migration_data(self, auth_context, project_id):
		url = join_url(self._api_root, 'get-project-migration-data')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'project_id': project_id})
		return result

	def get_access_control_entries_by_authorizable_id(self, auth_context, project_id):
		url = join_url(self._api_root, 'get-access-control-entries-by-privilege-id')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'privilege-id': 'viewAccess'})
		return result

	def get_valid_change_data_resource_host_destinations(self, auth_context, data_id):
		url = join_url(self._api_root, 'get-valid-change-data-resource-host-destinations')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'data-resource-id': data_id})
		return result

	def get_permission_mode(self, auth_context):
		url = join_url(self._api_root, 'get-permission-mode')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={})
		return result

	def get_inherited_default_host_server(self, auth_context, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-host-server')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-group-id': resource_group_id})
		return result

	# def get_backups_with_unique_resource(self, auth_context):
	# 	url = join_url(self._api_root, 'get-backups-with-unique-resource')
	# 	result = self.refresh_on_expiration(requests.post, auth_context, url, params={})
	# 	return result

	def get_log_entries_by(self, auth_context, scope, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entries-by-' + scope)
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={**filters, **criterion})
		return result

	def get_log_entry_unique(self, auth_context, scope, id_type, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entry-unique-' + scope)
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'id-type': id_type, **filters, **criterion})
		return result

	def create_log_entries_export_file(self, auth_context, id_type, filters={}, criterion={}):
		url = join_url(self._api_root, 'create-log-entries-export-file')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'id-type': id_type, **filters, **criterion})
		return result

	# todo: where's the file?
	#def export_log_entries(self, auth_context, export_id, filename):
	#	url = join_url(self._api_root, 'export-log-entries')
	#	result = self.refresh_on_expiration(requests.get, auth_context, url, params={'export-id': export_id, 'file-name': filename}, json={})
	#	return result

	# todo: /management/latest/set-floating-feature?

	# note: deprecated?
	def download_portal_server_logs(self, session_id, filepath):
		url = join_url(self._api_root, 'download-portal-server-logs')
		result = requests.get(url, params={'session-id': session_id})
		with open (filepath, 'wb') as f:
			f.write(result.content)

	# note: deprecated?
	def download_portal_server_database(self, session_id, filepath):
		url = join_url(self._api_root, 'download-portal-server-database')
		result = requests.get(url, params={'session-id': session_id})
		with open (filepath, 'wb') as f:
			f.write(result.content)

	def get_server_license_info(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/get-server-license-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def get_allocated_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/get-allocated-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def get_allocated_licenses_by_criterion(self, auth_context, criterion=None):
		url = join_url(self._api_root, 'ticket-generator/get-allocated-licenses-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json=criterion)
		return result	

	def count_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/count-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def count_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/count-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def count_versioned_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/count-versioned-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def count_expiring_licenses(self, auth_context, days):
		url = join_url(self._api_root, 'ticket-generator/count-expiring-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'remaining-days-treshold': days}, json={})
		return result

	def count_allocated_licenses_by_criterion(self, auth_context, criterion=None):
		url = join_url(self._api_root, 'ticket-generator/count-allocated-licenses-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json=criterion)
		return result	

	def get_license_infos(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/get-license-infos')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result	

	# todo: /management/latest/ticket-generator/assign-license
	# todo: /management/latest/ticket-generator/assign-versioned-license
	# todo: /management/latest/ticket-generator/revoke-license

	# todo: /management/latest/upload-data", _, y, "application/octet-stream

	def set_company_logo(self, session_id, mime_type):
		tk.Tk().withdraw()
		file_path = filedialog.askopenfilename()
		with open (file_path, 'rb') as file:
			url = join_url(self._api_root, 'set-company-logo')
			result = requests.post(url, data=file,  params={'session-id': session_id, 'mime-type': mime_type}, headers={ 'Content-Type': 'application/octet-stream' })
		return result	

	# note: 404?
	#def get_users_quota_info(self, auth_context):
	#	url = join_url(self._api_root, 'get-users-quota-info')
	#	result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
	#	return result	

	# todo: /management/latest/resolve-path
	# todo: /management/latest/upgrade
	# todo: /management/latest/start-downgrade-process
	# todo: /management/latest/cancel-downgrade-process
	# todo: /management/latest/downgrade
	# todo: /management/latest/check-manual-downgrade-step
	# todo: /management/latest/check-auto-downgrade-ace-count
	# todo: /management/latest/register-major-version
	# todo: /management/latest/activate-server

	# note: 404?
	#def get_message_server(self, auth_context):
	#	url = join_url(self._api_root, 'get-message-server')
	#	result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
	#	return result

	# todo: /management/latest/get-online-platforms-for-users-by-id-list

	# todo: /management/latest/insert-bimcloud-project
	# todo: /management/latest/insert-team
	# todo: /management/latest/add-to-teams
	# todo: /management/latest/remove-from-teams

	# todo: /management/latest/get-user-by-username
	# todo: /management/latest/contains-user-by-username
	# todo: /management/latest/get-users-by-authorizable-ids

	def set_user_password(self, auth_context, user_id, password, cur_password):
		url = join_url(self._api_root, 'set-user-password')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'user-id': user_id}, json={'password': password, 'current-password': cur_password})
		return result

	# todo: /management/latest/set-user-photo
	# todo: /management/latest/delete-user-photo
	# todo: /management/latest/get-user-photo?

	def reset_user_password(self, auth_context, user_name):
		url = join_url(self._api_root, 'reset-user-password')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'username': user_name}, json={})
		return result

	def send_email(self, auth_context, ids, subject, message):
		url = join_url(self._api_root, 'send-email')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': ids, 'subject': subject, 'message': message})
		return result

	# todo: /management/latest/import-authorizables
	# todo: /management/latest/get-authorizable-position-by-criterion
	# todo: /management/latest/get-inherited-default-library-upload-folder

	def get_folder_size_data(self, auth_context, folder_id):
		url = join_url(self._api_root, 'get-folder-size-data')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'folder-id': folder_id}, json={})
		return result

	# todo: management/latest/insert-change-notification-subscription
	# todo: management/latest/subscribe-to-resources-by-criterion

	# note: null?
	def subscribe_to_resource_by_criterion(self, auth_context, criterion=None):
		url = join_url(self._api_root, 'subscribe-to-resources-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'user-id': 'c615f63a-b4b3-4358-8608-1cdbd76aad73'}, json=criterion)
		return result

	# todo: /management/latest/delete-change-notification-subscription
	# todo: /management/latest/unsubscribe-from-resources-by-criterion
	# todo: /management/latest/remove-all-change-notification-subscriptions

	def get_blob_server_ids(self, auth_context):
		url = join_url(self._api_root, 'get-blob-server-ids')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	# todo: /management/latest/set-blob-server-ids
	# todo: /management/latest/start-fixing-blob-server-consistency
	# todo: /management/latest/start-model-server
	# todo: /management/latest/stop-model-server
	# todo: /management/latest/restart-model-server

	# note: fail
	def get_model_server_info(self, auth_context):
		url = join_url(self._api_root, 'get-model-server-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'model-server-url': 'http://162.55.83.203:25001/'}, json={})
		return result

	def has_model_server_data(self, auth_context):
		url = join_url(self._api_root, 'has-model-server-data')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'model-server-id': '9671af7f-2a80-9d1d-88ff-b3f1dbd8602f'}, json={})
		return result

	# todo: /management/latest/sync-model-server-resources-into-folder
	def get_local_model_servers_data(self, auth_context):
		url = join_url(self._api_root, 'get-local-model-servers-data')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	# todo: /management/latest/get-hosted-resources
	# todo: /management/latest/wait-for-deferred-tasks

	# todo: /management/latest/get-access-control-entries-by-resource-id
	# todo: /management/latest/get-access-control-entries-by-authorizable-id
	# todo: /management/latest/get-access-control-entries-by-privilege-id
	# todo: /management/latest/get-access-control-entry-effective-targets
	# todo: /management/latest/get-access-control-entry-effective-authorizables

	# todo: /management/latest/get-directory-service-sync-statuses-by-directory-service-id

	# todo: /management/latest/create-directory-service-preview
	# todo: /management/latest/get-directory-service-preview-items
	# todo: /management/latest/count-directory-service-preview-items
	# todo: /management/latest/remove-directory-service-preview

	# todo: /management/latest/test-directory-service-connection
	# todo: /management/latest/get-directory-service-base-dns
	# todo: /management/latest/synchronize-directory-service
	# todo: /management/latest/delete-directory-service

	# note: check
	def export_library(self, auth_context, library_id, auto_backup=False, man_backup=False):
		url = join_url(self._api_root, 'export-library')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'library-id': library_id, 'url-root': self.manager_url, 'include-automatic-backups': auto_backup, 'include-manual-backups': man_backup}, json={})
		return result

	# todo: /management/latest/import-library-get-url
	# todo: /management/latest/import-library-as-new

	def duplicate_library(self, auth_context, library_id, name):
		url = join_url(self._api_root, 'duplicate-library')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'library-id': library_id, 'library-name': name}, json={})
		return result

	def get_parent_permission_category(self, auth_context, permission_id):
		url = join_url(self._api_root, 'get-parent-permission-category')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'permission-id': permission_id}, json={})
		return result

	def get_parent_permission_sets(self, auth_context, permission_id):
		url = join_url(self._api_root, 'get-parent-permission-sets')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'permission-id': permission_id}, json={})
		return result

	def get_permissions(self, auth_context, target_resource_type):
		url = join_url(self._api_root, 'get-permissions')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'target-resource-type': target_resource_type}, json={})
		return result

	def get_permissions_by_name(self, auth_context, target_resource_type, name):
		url = join_url(self._api_root, 'get-permissions-by-name')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'target-resource-type': target_resource_type, 'permission-name': name}, json={})
		return result

	def get_permission_set_child_permission(self, auth_context, permission_set_id):
		url = join_url(self._api_root, 'get-permission-set-child-permissions')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'permission-set-id': permission_set_id}, json={})
		return result

	def get_permission_category_child_permissions(self, auth_context, permission_category_id):
		url = join_url(self._api_root, 'get-permission-category-child-permissions')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'permission-category-id': permission_category_id}, json={})
		return result

	def get_permission_categories(self, auth_context, target_resource_type):
		url = join_url(self._api_root, 'get-permission-categories')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'target-resource-type': target_resource_type}, json={})
		return result

	def export_project(self, auth_context, project_id, auto_backup=False, man_backup=False):
		url = join_url(self._api_root, 'export-project')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'project-id': project_id, 'url-root': self.manager_url, 'include-automatic-backups': auto_backup, 'include-manual-backups': man_backup}, json={})
		return result





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
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={ 'resource-id': resource_id })
		return result

	def get_resources_by_criterion(self, auth_context, criterion, options=None):
		if criterion is None:
			raise ValueError('"criterion"" expected.')

		url = join_url(self._api_root, 'get-resources-by-criterion')
		params = {}
		if isinstance(options, dict):
			for key in options:
				params[key] = options[key]

		result = self.refresh_on_expiration(requests.post, auth_context, url, params=params, json=criterion)
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
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={ 'parent-id': parent_id }, json=directory)
		assert isinstance(result, str), 'Result is not a string.'
		return result

	def delete_resource_group(self, auth_context, directory_id):
		url = join_url(self._api_root, 'delete-resource-group')
		result = self.refresh_on_expiration(requests.delete, auth_context, url, params={ 'resource-id': directory_id })
		return result

	def delete_resources_by_id_list(self, auth_context, ids):
		url = join_url(self._api_root, 'delete-resources-by-id-list')
		result = self.refresh_on_expiration(requests.post, auth_context, url, json={ 'ids': ids })
		return result

	def delete_blob(self, auth_context, blob_id):
		url = join_url(self._api_root, 'delete-blob')
		self.refresh_on_expiration(requests.delete, auth_context, url, params={'resource-id': blob_id })

	def update_blob(self, auth_context, blob):
		url = join_url(self._api_root, 'update-blob')
		self.refresh_on_expiration(requests.put, auth_context, url, json=blob)

	def update_blob_parent(self, auth_context, blob_id, body):
		url = join_url(self._api_root, 'update-blob-parent')
		self.refresh_on_expiration(requests.post, auth_context, url, params={ 'blob-id': blob_id }, json=body)

	def get_blob_changes_for_sync(self, auth_context, path, resource_group_id, from_revision):
		url = join_url(self._api_root, 'get-blob-changes-for-sync')
		request = {
 			'path': path,
			'resourceGroupId': resource_group_id,
			'fromRevision': from_revision
		}
		result = self.refresh_on_expiration(requests.post, auth_context, url, json=request)
		assert isinstance(result, object), 'Result is not an object.'
		return result

	# note: null?
	def get_inherited_default_blob_server_id(self, auth_context, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-blob-server-id')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={ 'resource-group-id': resource_group_id })
		return result

	def get_job(self, auth_context, job_id):
		url = join_url(self._api_root, 'get-job')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={ 'job-id': job_id })
		return result

	def abort_job(self, auth_context, job_id):
		url = join_url(self._api_root, 'get-job')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={ 'job-id': job_id })
		return result

	def get_ticket(self, auth_context, resource_id):
		url = join_url(self._api_root, 'ticket-generator/get-ticket')
		request = {
			'type': 'freeTicket',
			'resources': [resource_id],
			'format': 'base64'
		}
		result = self.refresh_on_expiration(requests.post, auth_context, url, False, json=request)
		assert isinstance(result, bytes), 'Result is not a bytes.'
		result = result.decode('utf-8')
		return result

	def get_user(self, auth_context, user_id):
		url = join_url(self._api_root, 'get-user')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={ 'user-id': user_id })
		return result

	def refresh_on_expiration(self, req, auth_context, url, responseJson=True, **kwargs):
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