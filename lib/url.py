from urllib.parse import urlparse

def join_url(*parts):
	joined = '/'.join(map(lambda part: part.strip('/'), parts))
	if len(parts):
		if parts[0].startswith('/'):
			joined = '/' + joined
		if parts[-1].endswith('/'):
			joined += '/'
	return joined

def add_params(url, params):
	result = url
	if url[-1] == '/':
		result = url[:-1]

	first = True
	for key, value in params.items():
		if first:
			result += f'?{key}={value}'
			first = False
		else:
			result += f'&{key}={value}'

	return result

def is_url(url):
	try:
		result = urlparse(url)
		return all([result.scheme, result.netloc])
	except ValueError:
		return False

def parse_url(url):
	return urlparse(url)