import os
import re
import csv
import getpass
import shutil
import zipfile
from jinja2 import Environment, FileSystemLoader
from cromwell import Cromwell


def check_identifier(identifier):
    matchObj = re.match(r'^[a-zA-Z][a-zA-Z0-9_]+$', identifier, re.M|re.I)
    if matchObj:
        return True
    else:
        return False


def install_app(app_dir, app_file):
    app_name = os.path.splitext(os.path.basename(app_file))[0]
    dest_namelist = [os.path.join(app_name, 'inputs'), 
                    os.path.join(app_name, 'workflow.wdl'), 
                    os.path.join(app_name, 'tasks.zip')]

    app_file_handler = zipfile.ZipFile(app_file)

    def check_app(app_file_handler):
        namelist = app_file_handler.namelist()
        if len([ path for path in dest_namelist if path in namelist ]) == 3:
            return True
        else:
            return False

    if check_app(app_file_handler):
        app_file_handler.extractall(app_dir, dest_namelist)
        print("Install %s successfully." % app_name)
    else:
        raise Exception("Not a valid app.")


def uninstall_app(app_dir):
    answer = ''
    while answer.upper() not in ("YES", "NO", "Y", "N"):
        answer = raw_input("Enter Yes/No: ")
        answer = answer.upper()
        if answer == "YES" or answer == "Y":
            shutil.rmtree(app_dir)
            print("Uninstall %s successfully." % os.path.basename(app_dir))
        elif answer == "NO" or answer == "N":
            print("Cancel uninstall %s." % os.path.basename(app_dir))
        else:
            print("Please enter Yes/No.")


def parse_samples(file):
    reader = csv.DictReader(open(file, 'rb'))
    dict_list = []
    
    for line in reader:
        dict_list.append(line)

    return dict_list

def render_app(app_path, template_file, data):
    env = Environment(loader=FileSystemLoader(app_path))
    template = env.get_template(template_file)
    return template.render(**data)

def write(path, filename, data):
    with open(os.path.join(path, filename), 'w') as f:
        f.write(data)

def submit_workflow(wdl, inputs, dependencies, label, username=getpass.getuser(), 
                    server='localhost', extra_options=None, labels_dict=None):
    labels_dict = kv_list_to_dict(label) if kv_list_to_dict(label) != None else {}
    labels_dict['username'] = username
    cromwell = Cromwell(host=server)
    result = cromwell.jstart_workflow(wdl_file=wdl, json_file=inputs, dependencies=dependencies,
                                      extra_options=kv_list_to_dict(extra_options), 
                                      custom_labels=labels_dict)
    result['port'] = cromwell.port

    return result

def kv_list_to_dict(kv_list):
    """
    Converts a list of kv pairs delimited with colon into a dictionary.
    :param kv_list: kv list: ex ['a:b', 'c:d', 'e:f']
    :return: a dict, ex: {'a': 'b', 'c': 'd', 'e': 'f'}
    """
    new_dict = dict()
    if kv_list:
        for item in kv_list:
            (key, val) = item.split(':')
            new_dict[key] = val
        return new_dict
    else:
        return None