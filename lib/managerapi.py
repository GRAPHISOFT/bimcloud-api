import requests
import webbrowser
import tkinter as tk
from tkinter import filedialog
from datetime import datetime, timedelta

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

	def close_session(self, session_id):
		url = join_url(self._api_root, 'close-session')
		result = requests.post(url, params={'session-id': session_id})
		return result

	def ping_session(self, session_id):
		url = join_url(self._api_root, 'ping-session')
		result = requests.post(url, params={'session-id': session_id})
		return result

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

	# CUSTOM

	def get_items_by_criterion(self, auth_context, scope=None, criterion=None, options=None):
		url = join_url(self._api_root, 'get-' + scope + '-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={})
		return result

	def get_log_entries_by(self, auth_context, scope, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entries-by-' + scope)
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={**filters, **criterion})
		return result

	def get_log_entry_unique(self, auth_context, scope, id_type, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entry-unique-' + scope)
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'id-type': id_type, **filters, **criterion})
		return result

	# DEFAULT

	def get_inherited_resource_backup_schedulers(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-inherited-resource-backup-schedulers')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-id': resource_id})
		return result


	# todo: /management/latest/insert-

	def monitoring_status(self, auth_context):
		""" Returns status of bimcloud metrics.
        	Returns:
				str: unavailable / enabled
		"""
		url = join_url(self._api_root, 'monitoring/status')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_metric_levels(self, auth_context):
		""" Returns all available metric levels.
        	Returns:
				list
		"""
		url = join_url(self._api_root, 'monitoring/metric-levels')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_known_metric_definitions(self, auth_context):
		""" Returns all potential metric types
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'monitoring/known-metric-definitions')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_stored_namespaces(self, auth_context):
		""" Returns active namespace for this bimcloud.
        	Returns:
				list
		"""
		url = join_url(self._api_root, 'monitoring/stored-namespaces')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_stored_metric_definitions(self, auth_context):
		""" Returns stored named metric types.
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'monitoring/stored-metric-definitions')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_metric_bounds(self, auth_context, metric, namespace='portalServer'):
		""" Returns range bounds for the chosen metric.
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'monitoring/metric-bounds/' + namespace + '/' + metric)
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_has_metric(self, auth_context, metric, namespace='portalServer'):
		""" Checks whether required metrics exist.
        	Returns:
				boolean
		"""
		url = join_url(self._api_root, 'monitoring/has-metrics/' + namespace + '/' + metric)
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def monitoring_metrics(self, auth_context, metric, namespace='portalServer', _from=60, _to=0, level=0):
		""" Retrieves timestamp & values of the chosen metrics and time period.
			Applicable metrics:
				portalServer/machine.totalMemory
				portalServer/machine.freeMemory
				portalServer/machine.cpuUsagePercent
				portalServer/api.requestsPerSec
				portalServer/api.requestThroughoutPerSec
				portalServer/api.responseThroughoutPerSec
				portalServer/app.users
				portalServer/app.projects
				portalServer/app.activeUsers
				portalServer/app.activeProjects
				portalServer/disk.totalDataSize
				portalServer/disk.freeDataSize
				# for additional ones see monitoring_known_metric_definitions() method
        	Returns:
				dict
		"""
		now = datetime.now()
		time_from = int((now - timedelta(seconds=_from)).timestamp() * 1000)
		time_till = int((now - timedelta(seconds=_to)).timestamp() * 1000)

		url = join_url(self._api_root, 'monitoring/metrics/' + namespace + '/' + metric + '/' + str(level))
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'from': time_from, 'to': time_till}, json={})
		return result

	def monitoring_last_metrics(self, auth_context, metric, namespace='portalServer', count=1, level=0):
		""" Retrieves timestamp & values of the chosen metrics.
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'monitoring/last-metrics/' + namespace + '/' + metric + '/' + str(level))
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'count': count}, json={})
		return result

	def monitoring_last_metric(self, auth_context, metric, namespace='portalServer', level=0):
		""" Retrieves latest timestamp & values of the chosen metrics.
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'monitoring/last-metric/' + namespace + '/' + metric + '/' + str(level))
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def get_inherited_resource_backup_schedulers(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-inherited-resource-backup-schedulers')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-id': resource_id})
		return result

	def get_inherited_blob_revision_retention_policy(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-inherited-blob-revision-retention-policy')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-id': resource_id})
		return result

	def get_lazy_list_position_by_criterion(self, auth_context, resource_id):
		url = join_url(self._api_root, 'get-lazy-list-position-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-id': resource_id, 'sort-by': 'id', 'sort-direction': 'asc'})
		return result

	# todo: /management/latest/gsid/authenticate-and-connect
	# todo: /management/latest/gsid/pending-gsid-connection?

	# test
	def set_user_password_with_token(self, auth_context, token, password):
		url = join_url(self._api_root, 'set-user-password-with-token')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'token': token}, json={'password': password})
		return result

	def reset_user_password(self, auth_context, user_name):
		url = join_url(self._api_root, 'reset-user-password')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'username': user_name}, json={})
		return result

	# todo: /management/latest/ensure-session-has-license

	def get_edition_status(self, auth_context):
		""" Retrieves information about downgrading process
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'get-edition-status')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_ping(self, auth_context):
		""" Pings server in the network
        	Returns:
				dict
		"""
		url = join_url(self.manager_url, 'ping')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_network_info(self, auth_context):
		""" Retrieves hostname, port and ip address of the bimcloud server
        	Returns:
				list
		"""
		url = join_url(self._api_root, 'get-network-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_server_info(self, auth_context):
		""" Retrieves a full information about running bimcloud
        	Returns:
				dict
		"""
		url = join_url(self.manager_url, 'get-server-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_webui_config(self, auth_context):
		""" Retrieves configuration settings for manager UI
        	Returns:
				dict
		"""
		url = join_url(self.manager_url, 'get-webui-config')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_library_root_path(self, auth_context):
		""" Retrieves root path for the library folder
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'get-library-root-path')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_floating_features(self, auth_context):
		url = join_url(self._api_root, 'get-floating-features')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_server_public_key(self, auth_context):
		""" Retrieves server public key
        	Returns:
				byte string
		"""	
		url = join_url(self._api_root, 'get-server-public-key')
		response = requests.get(url, params={})
		result = self.process_response(response, json=False)
		return result

	def get_company_logo(self, auth_context):
		""" Grabs company logo image if exists
        	Returns:
				binary
		"""	
		url = join_url(self._api_root, 'get-company-logo')
		response = requests.get(url, params={})
		result = self.process_response(response, json=False)
		return result

	def get_locale_config(self, auth_context):
		""" Retrieves available locales
        	Returns:
				dict
		"""	
		url = join_url(self._api_root, 'get-locale-config')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	def get_locale_by_id(self, auth_context, lang_id):
		""" Retrieves all localisation texts for the given locale
			Parameters:
				lang_id (string):		# localisation key (en, it, uk...)
        	Returns:
				dict
		"""	
		url = join_url(self._api_root, 'get-locale-by-id')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'lang-id': lang_id})
		return result

	def get_announcement(self, auth_context):
		url = join_url(self._api_root, 'get-announcement')
		result = self.refresh_on_expiration(requests.get, auth_context, url)
		return result

	# todo: /management/latest/begin-transaction
	# todo: /management/latest/commit
	# todo: /management/latest/abort

	def get_effective_permissions(self, auth_context, resource_type, resource_id, authorizable_id):
		#resource-type: authorizables, privileges, resources
		url = join_url(self._api_root, 'get-effective-permissions')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-type': resource_type, 'resource-id': resource_id, 'authorizable-id': authorizable_id}, json={})
		return result

	def get_effective_permissions_by_criterion(self, auth_context, resource_type, criterion=None):
		url = join_url(self._api_root, 'get-effective-permissions-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-type': resource_type}, json=criterion)
		return result

	# todo: /management/latest/get-effective-permissions-by-ids

	def get_project_migration_data(self, auth_context, project_id):
		url = join_url(self._api_root, 'get-project-migration-data')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'project_id': project_id})
		return result

	# todo: /management/latest/put-project-migration-data
	# todo: /management/latest/change-data-resource-host

	def get_access_control_entries_by_authorizable_id(self, auth_context, project_id):
		url = join_url(self._api_root, 'get-access-control-entries-by-privilege-id')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'privilege-id': 'viewAccess'})
		return result

	def get_valid_change_data_resource_host_destinations(self, auth_context, data_id):
		url = join_url(self._api_root, 'get-valid-change-data-resource-host-destinations')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'data-resource-id': data_id})
		return result

	# todo: /management/latest/send-test-email

	def get_permission_mode(self, auth_context):
		url = join_url(self._api_root, 'get-permission-mode')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={})
		return result

	def force_logout_user_from_project(self, auth_context, project_id, user_id):
		url = join_url(self._api_root, 'force-logout-user-from-project')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'project-id': project_id, 'user-id': user_id}, json={})
		return result

	def force_logout_all_users_from_project(self, auth_context, project_id):
		url = join_url(self._api_root, 'force-logout-all-users-from-project')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'project-id': project_id}, json={})
		return result

	def force_logout_all_users_from_projects(self, auth_context):
		url = join_url(self._api_root, 'force-logout-all-users-from-projects')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={})
		return result

	def get_inherited_default_host_server(self, auth_context, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-host-server')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-group-id': resource_group_id})
		return result

	# note: null?
	def get_inherited_default_blob_server_id(self, auth_context, resource_group_id):
		url = join_url(self._api_root, 'get-inherited-default-blob-server-id')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={ 'resource-group-id': resource_group_id })
		return result

	# todo: /management/latest/duplicate-folder
	# todo: /management/latest/duplicate-blob
	# todo: /management/latest/mount-unknown-data-resource-to-missing
	# todo: /management/latest/mount-unknown-data-resource-as-new

	# note: fail
	def get_backup(self, auth_context, backup_id):
		url = join_url(self._api_root, 'get-backup')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'backup-id': backup_id}, json={})
		# result = requests.get(url, params={'session-id': session_id, 'backup-id': backup_id})
		return result

	def get_backups(self, auth_context):
		url = join_url(self._api_root, 'get-backups')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	# note: fail
	def get_backups_with_unique_resource(self, auth_context):
		url = join_url(self._api_root, 'get-backups-with-unique-resource')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	# note: fail
	def count_backups(self, auth_context):
		url = join_url(self._api_root, 'count-backups')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	# note: fail
	def get_backups_by_criterion(self, auth_context, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-backups-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={**filters, **criterion})
		return result

	# 	/management/latest/get-backups-with-unique-resource
	# 	/management/latest/get-backups-with-unique-resource-by-criterion
	# 	/management/latest/count-backups-by-criterion

	def download_backup(self, session_id, resource_id, backup_id):
		url = join_url(self._api_root, 'download-backup')
		# result = self.refresh_on_expiration(requests.get, auth_context, url, params={'resource-id': resource_id, 'backup-id': backup_id}, json={})
		result = requests.get(url, params={ 'session-id': session_id, 'resource-id': resource_id, 'backup-id': backup_id})
		with open("C:\\Users\\i.yurasov\\Desktop\\dev\\backup.BIMProject25", "wb") as file:
			file.write(result.content)

	def get_log_entries_by_users(self, auth_context, usersIds, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entries-by-users')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': usersIds, **filters, **criterion})
		return result

	def get_log_entries_by_projects(self, auth_context, projectsIds, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entries-by-projects')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': projectsIds, **filters, **criterion})
		return result

	def get_log_entries_by_servers(self, auth_context, serversIds, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entries-by-servers')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': serversIds, **filters, **criterion})
		return result

	# note: inputs
	def get_log_entry_unique_users(self, auth_context, usersIds, id_type, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entry-unique-users')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': usersIds, 'id-type': id_type, **filters, **criterion})
		return result

	# note: inputs
	def get_log_entry_unique_projects(self, auth_context, projectsIds, id_type, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-log-entry-unique-users')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': projectsIds,  'id-type': id_type, **filters, **criterion})
		return result

	# note: inputs
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

	def get_server_license_info(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/get-server-license-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def get_allocated_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/get-allocated-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def count_allocated_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/count-allocated-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def get_allocated_licenses_by_criterion(self, auth_context, filters=None, criterion=None):
		url = join_url(self._api_root, 'ticket-generator/get-allocated-licenses-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={**filters, **criterion})
		return result	

	def count_allocated_licenses_by_criterion(self, auth_context, filters=None, criterion=None):
		url = join_url(self._api_root, 'ticket-generator/count-allocated-licenses-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={**filters, **criterion})
		return result

	# todo: /management/latest/ticket-generator/assign-license
	# todo: /management/latest/ticket-generator/assign-versioned-license
	# todo: /management/latest/ticket-generator/revoke-license

	def count_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/count-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def count_versioned_licenses(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/count-versioned-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def get_license_infos(self, auth_context):
		url = join_url(self._api_root, 'ticket-generator/get-license-infos')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	def count_expiring_licenses(self, auth_context, days):
		url = join_url(self._api_root, 'ticket-generator/count-expiring-licenses')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'remaining-days-treshold': days}, json={})
		return result

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
	def get_message_server(self, auth_context):
		url = join_url(self._api_root, 'get-message-server')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={}, json={})
		return result

	# todo: /management/latest/get-online-platforms-for-users-by-id-list

	# todo: /management/latest/insert-bimcloud-project
	# todo: /management/latest/insert-team
	# todo: /management/latest/add-to-teams
	# todo: /management/latest/remove-from-teams

	# todo: /management/latest/

	def get_user_by_username(self, auth_context, username):
		url = join_url(self._api_root, 'get-user-by-username')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'user-username': username}, json={})
		return result
		
	# todo: /management/latest/contains-user-by-username

	def contains_user_by_username(self, auth_context, username):
		url = join_url(self._api_root, 'contains-user-by-username')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'user-username': username}, json={})
		return result

	def get_users_by_authorizable_ids(self, auth_context, authIds):
		url = join_url(self._api_root, 'get-users-by-authorizable-ids')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'authorizable-ids': authIds}, json={})
		return result

	def set_user_password(self, auth_context, user_id, password, cur_password):
		url = join_url(self._api_root, 'set-user-password')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'user-id': user_id}, json={'password': password, 'current-password': cur_password})
		return result

	# todo: /management/latest/set-user-photo
	# todo: /management/latest/delete-user-photo
	# todo: /management/latest/get-user-photo?

	def send_email(self, auth_context, ids, subject, message):
		url = join_url(self._api_root, 'send-email')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': ids, 'subject': subject, 'message': message})
		return result

	# todo: /management/latest/import-authorizables (users?)
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
	def get_model_server_info(self, auth_context, http_addres):
		url = join_url(self._api_root, 'get-model-server-info')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'model-server-url': http_addres}, json={})
		return result

	def has_model_server_data(self, auth_context, server_id):
		""" Retrieves data status for the chosen server
			Parameters:
				server_id (str)		# uuid of the model server
        	Returns:
				dict
		"""
		url = join_url(self._api_root, 'has-model-server-data')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'model-server-id': server_id}, json={})
		return result

	# todo: /management/latest/sync-model-server-resources-into-folder

	def get_local_model_servers_data(self, auth_context):
		""" Retrieves information about local server
        	Returns:
				dict
		"""
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

	def export_project_list(self, session_id, resource_group_id, filename):
		url = join_url(self._api_root, 'export-project-list')
		result = requests.get(url, params={'session-id': session_id, 'resource-group-id': resource_group_id, 'file-name': filename}, json={})
		with open ('C:\\Users\\i.yurasov\\Desktop\\dev\\' + filename, 'wb') as file:
			file.write(result.content)

	# todo: /management/latest/import-project-get-url
	# todo: /management/latest/import-project
	# todo: /management/latest/import-project-as-new

	def duplicate_project(self, auth_context, project_id, name):
		url = join_url(self._api_root, 'duplicate-project')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'project-id': project_id, 'project-name': name}, json={})
		return result

	# todo: /management/latest/insert-resource-backup-schedule
	# todo: /management/latest/create-server-backup
	# todo: /management/latest/cancel-server-backup

	def get_parent_user_groups(self, auth_context, authorizable_id):
		url = join_url(self._api_root, 'get-parent-user-groups')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'authorizable-id': authorizable_id}, json={})
		return result

	def get_user_group_child_users(self, auth_context, group_id):
		url = join_url(self._api_root, 'get-user-group-child-users')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'user-group-id': group_id}, json={})
		return result

	def get_user_group_child_user_groups(self, auth_context, group_id):
		url = join_url(self._api_root, 'get-user-group-child-user-groups')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={'user-group-id': group_id}, json={})
		return result

	def add_to_user_groups(self, auth_context, membersIds, groupsIds):
		url = join_url(self._api_root, 'add-to-user-groups')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'memberIds': membersIds, 'groupIds': groupsIds})
		return result

	def remove_from_user_groups(self, auth_context, membersIds, groupsIds):
		url = join_url(self._api_root, 'remove-from-user-groups')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'memberIds': membersIds, 'groupIds': groupsIds})
		return result

	# todo: /management/latest/delete-notifications-by-id-list

	def insert_private_tag(self, auth_context, name, color, tag_type='tag'):
		url = join_url(self._api_root, 'insert-private-tag')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'name': name, 'color': color, 'type': tag_type})
		return result

	# todo: input parameters
	#def update_private_tag(self, auth_context, tag_id, name, color, type='tag'):
	#	url = join_url(self._api_root, 'update-private-tag')
	#	result = self.refresh_on_expiration(requests.post, auth_context, url, params={'tagId': '7cb708ef-129b-446d-dff7-d7290082877f'}, json={})
	#	return result

	def remove_all_tags(self, auth_context):
		url = join_url(self._api_root, 'remove-all-tags')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={})
		return result

	def assign_private_tag(self, auth_context, resource_id, tag_id):
		url = join_url(self._api_root, 'assign-private-tag')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'resourceId': resource_id, 'tagId': tag_id})
		return result

	def unassign_private_tag(self, auth_context, resource_id, tag_id):
		url = join_url(self._api_root, 'unassign-private-tag')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'resourceId': resource_id, 'tagId': tag_id})
		return result

	def create_resource_backup(self, auth_context, resource_id, backup_type, name):
		url = join_url(self._api_root, 'create-resource-backup')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-id': resource_id, 'backup-type': backup_type, 'backup-name': name}, json={})
		return result

	def keep_resource_backup(self, auth_context, resource_id, backup_id, backup_name):
		url = join_url(self._api_root, 'keep-resource-backup')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-id': resource_id, 'backup-id': backup_id, 'backup-name': backup_name}, json={})
		return result

	def delete_resource_backup(self, auth_context, resource_id, backup_id):
		url = join_url(self._api_root, 'delete-resource-backup')
		result = self.refresh_on_expiration(requests.delete, auth_context, url, params={'resource-id': resource_id, 'backup-id': backup_id}, json={})
		return result

	def restore_resource_backup(self, auth_context, resource_id, backup_id):
		url = join_url(self._api_root, 'restore-resource-backup')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-id': resource_id, 'backup-id': backup_id}, json={})
		return result

	def restore_resource_backup_as_new(self, auth_context, server_id, resource_id, backup_id, parent_id, name):
		url = join_url(self._api_root, 'restore-resource-backup-as-new')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'model-server-id': server_id, 'resource-id': resource_id, 'backup-id': backup_id, 'resource-name': name, 'parent-id': parent_id}, json={})
		return result

	def rename_resource_backup(self, auth_context, resource_id, backup_id, name):
		url = join_url(self._api_root, 'rename-resource-backup')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={'resource-id': resource_id, 'backup-id': backup_id, 'backup-name': name}, json={})
		return result

	def get_resource_backups_by_criterion(self, auth_context, resourcesIds, filters={}, criterion={}):
		url = join_url(self._api_root, 'get-resource-backups-by-criterion')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={}, json={'ids': resourcesIds, **filters, **criterion})
		return result

	# todo: /management/latest/abort-job

	# todo: /management/latest/gsid/create-gsid-user
	# todo: /management/latest/gsid/send-connect-email
	# todo: /management/latest/gsid/pending-gsid-connection-by-userid
	# todo: /management/latest/gsid/global-license-usage
	# todo: /management/latest/gsid/user-byol-enable
	# todo: /management/latest/gsid/user-byol-disable
	# todo: /management/latest/gsid/assign-user-global-license"
	# todo: /management/latest/gsid/remove-user-global-license

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

	def get_job(self, auth_context, job_id):
		url = join_url(self._api_root, 'get-job')
		result = self.refresh_on_expiration(requests.get, auth_context, url, params={ 'job-id': job_id })
		return result

	def abort_job(self, auth_context, job_id):
		url = join_url(self._api_root, 'get-job')
		result = self.refresh_on_expiration(requests.post, auth_context, url, params={ 'job-id': job_id })
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