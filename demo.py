import argparse
import sys
import lib

def start():
	parser = argparse.ArgumentParser()
	parser.add_argument('-m', '--manager', required=True, help='Url of BIMcloud Manager.')
	parser.add_argument('-c', '--clientid', required=True, help='3rd party client id (arbitrary unique string, your domain for example).')
	parser.add_argument('-d', '--debug', required=False, help='Debug exceptions.', action='store_true')
	parser.add_argument('-u', '--user', required=False, help='User name for simple authentication if BIMcloud supports it.', default=None)
	parser.add_argument('-p', '--password', required=False, help='Password for simple authentication if BIMcloud supports it.', default=None)
	parser.add_argument('-t', '--tempdir', required=False, help='Temporary directory to store downloaded files. Default is the system temporary directory.', default=None)
	args = parser.parse_args()

	un_pw = None
	if args.user is not None and args.password is not None:
		un_pw = (args.user, args.password)

	wf = lib.Workflow(args.manager, args.clientid, un_pw, args.tempdir)
	try:
		wf.run()
	except Exception as err:
		print(getattr(err, 'message', str(err) or repr(err)), file=sys.stderr)
		if args.debug:
			raise err
		else:
			exit(1)

if __name__ == '__main__':
	start()
