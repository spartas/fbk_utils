#!/usr/bin/env python3
import os 
import json
import urllib
import urllib.request
import sqlite3
import sys

obj_config = None
default_obj_config = obj_config = {
	"timefilter"	: {},
	"albums" 		: [],
	"tagline"		: "",
	"graph"			: {},
}

def validate_access_token( obj_config ):
	#obj_config['graph']['access_token'] = "blarg"

	if not obj_config['graph']['access_token']:
		print("No access_token was specified. Unable to process requests.")
		sys.exit(3)



	url_token_req = "https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=https://www.facebook.com/connect/login_success.html&response_type=token" % (obj_config['graph']['client_id'])
	#res = urllib.request.urlopen(url_token_req)
	#print(res.read())


	return obj_config

def parse_config( str_configpath, validate_token=False ):
	if( not os.path.isfile(str_configpath)):
		print("The specified config filter file, %s, does not exist." % (str_configpath))
		sys.exit(1)

	configfile = open(str_configpath, 'r')
	obj_config = json.load(configfile)
	configfile.close()

	# Re-generate the keys for un-specified values in the JSON config file
	for conf_key in default_obj_config:
		if conf_key not in obj_config:
			obj_config[conf_key] = default_obj_config[conf_key]

	temp_timefilter = []
	for k in obj_config['timefilter']:
		temp_timefilter.extend(obj_config['timefilter'][k])

	obj_config['timefilter'] = temp_timefilter

	if( validate_token ):
		obj_config = validate_access_token( obj_config )

	return obj_config

