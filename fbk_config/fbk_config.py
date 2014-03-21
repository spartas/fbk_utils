#!/usr/bin/env python3
import os 
import json

default_obj_config = obj_config = {
	"timefilter"	: {},
	"albums" 		: [],
	"tagline"		: "",
	"graph"			: {},
}

def parse_config( str_configpath ):
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

	return obj_config

