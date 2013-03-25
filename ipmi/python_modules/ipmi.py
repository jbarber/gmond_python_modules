import sys
import re
import time
import copy
import string
import subprocess
import pwd

PARAMS = {}
METRICS = {
    'time' : 0,
    'data' : {}
}

METRICS_CACHE_MAX = 5

def validate_params(params):
    '''Validate parameters'''

    if 'timeout_bin' not in params:
        raise Exception("Missing timeout_bin parameter (path to timeout binary)")

    if 'ipmitool_bin' not in params:
        raise Exception("Missing ipmitool_bin parameter (path to ipmitool binary)")

    if 'ipmi_ip' in params:
        if not set(['username', 'password']).issubset(set(params)):
            raise Exception("Missing IPMI LAN 'username' and 'password' parameters")

    if 'sudo' in params:
        try:
            pw = pwd.getpwnam(params['sudo'])
        except Exception:
            raise Exception("sudo username '%s' not known on the system" % params['sudo'])

def create_cmd(params):
    '''Construct the command to get the IPMI data'''
    command = []

    if 'timeout_bin' in params:
        command.extend([ params['timeout_bin'], '3' ])

    if 'sudo' in params:
        command.extend([ 'sudo', '-u', params['sudo'] ])

    command.append(params['ipmitool_bin'])

    if 'ipmi_ip' in params:
        command.extend(['-H', params['ipmi_ip'], "-U" , params['username'], '-P', params['password'] ])

    command.append('sensor')
    return command

def get_metrics(params):
    """Return all metrics"""
    global METRICS

    new_metrics = {}
    units = {}
    command = create_cmd(params)

    if (time.time() - METRICS['time']) > METRICS_CACHE_MAX:
        p = subprocess.Popen(command, stdout=subprocess.PIPE).communicate()[0][:-1]

        for i, v in enumerate(p.split("\n")):
            data = v.split("|")
            try:
                metric_name = data[0].strip().lower().replace("+", "").replace(" ", "_")
                value = data[1].strip()

                # Skip missing sensors
                if re.search("(0x)", value ) or value == 'na':
                    continue

                # Extract out a float value
                vmatch = re.search("([0-9.]+)", value)
                if not vmatch:
                    continue
                metric_value = float(vmatch.group(1))

                new_metrics[metric_name] = metric_value
                units[metric_name] = data[2].strip().replace("degrees C", "C")
            except ValueError:
                continue
            except IndexError:
                continue

        METRICS = {
            'time':  time.time(),
            'data':  new_metrics,
            'units': units,
        }
        
    return METRICS

def get_value(name):
    """Return a value for the requested metric"""

    try:
        metrics = get_metrics(PARAMS)
        prefix_length = len(PARAMS['metric_prefix']) + 1
        name = name[prefix_length:] # remove prefix from name
        result = metrics['data'][name]
    except Exception:
        result = 0

    return result

def create_desc(skel, prop):
    d = skel.copy()
    for k,v in prop.iteritems():
        d[k] = v
    return d

def metric_init(params):
    descriptors = []
    Desc_Skel = {
        'name'        : 'XXX',
        'call_back'   : get_value,
        'time_max'    : 60,
        'value_type'  : 'float',
        'format'      : '%.5f',
        'units'       : 'count/s',
        'slope'       : 'both', # zero|positive|negative|both
        'description' : 'XXX',
        'groups'      : 'XXX',
        }

    for key in params:
        PARAMS[key] = params[key]

    validate_params(PARAMS)

    metrics = get_metrics(PARAMS)

    for item in metrics['data']:
        descriptors.append(create_desc(Desc_Skel, {
            'name'   : params['metric_prefix'] + "_" + item,
            'groups' : params['metric_prefix'],
            'units'  : metrics['units'][item]
            }))

    return descriptors

def metric_cleanup():
    '''Clean up the metric module.'''
    pass

#This code is for debugging and unit testing
if __name__ == '__main__':
    params = {
        "metric_prefix": "ipmi",
        "username":      "ADMIN",
        "password":      "secret",
        "timeout_bin":   "/usr/bin/timeout",
        "ipmitool_bin":  "/usr/bin/ipmitool",
        "sudo":          "root",
    }
    descriptors = metric_init(params)

    # Test parameter validation
    validate_params(params)

    # Show how we're going to get the results
    print(" ".join(create_cmd(params)))

    while True:
        for d in descriptors:
            v = d['call_back'](d['name'])
            print '%s = %s' % (d['name'],  v)
        print 'Sleeping 15 seconds'
        time.sleep(15)
