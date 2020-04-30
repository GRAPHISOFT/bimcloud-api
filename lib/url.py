from urllib.parse import urlparse

def join_url(*parts):
	joined = '/'.join(map(lambda part: part.strip('/'), parts))
	if len(parts):
		if parts[0].startswith('/'):
			joined = '/' + joined
		if parts[-1].endswith('/'):
			joined += '/'
	return joined

def is_url(url):
	try:
		result = urlparse(url)
		return all([result.scheme, result.netloc])
	except ValueError:
		return False

def parse_url(url):
	return urlparse(url)