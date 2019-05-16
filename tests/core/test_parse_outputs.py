import re
import json
from choppy.core.cromwell import Cromwell
import choppy.config as c


def parse_outputs():
    """
    Parse outputs from cromwell metadata.
    """
    # TODO: four level for loop is too bad, how to improve it?
    outputs = {}
    for metadata in get_workflow_metadata():
        calls = metadata.get('calls')
        # serveral tasks in calls
        for task_name in calls.keys():
            task_lst = calls.get(task_name)
            # may be several tasks have same task name.
            for task in task_lst:
                task_outputs = task.get('outputs')
                # one task have sevaral outputs.
                for output_key in task_outputs.keys():
                    key = '%s.%s' % (task_name, output_key)
                    output = outputs[key] = task_outputs.get(output_key)
                    # handle output directory
                    if isinstance(output, list):
                        pattern = r'^([-\w/:.]+%s).*$' % output_key
                        # MUST BE matched. Need assert or more friendly way?
                        matched = re.match(pattern, output[0])
                        output_dir = matched.groups()[0]
                        outputs[key] = output_dir

                stderr = '%s.stderr' % task_name
                stdout = '%s.stdout' % task_name
                outputs[stderr] = task.get('stderr')
                outputs[stdout] = task.get('stdout')
    return outputs


def get_workflow_metadata():
    host, port, auth = c.get_conn_info('remote')
    cromwell = Cromwell(host, port, auth)
    workflow_id_lst = ['ec30ad38-bc22-4c46-9693-7e9321d3e8ae']
    for workflow_id in workflow_id_lst:
        # TODO: handle network error.
        metadata = cromwell.query_metadata(workflow_id)
        yield metadata


outputs = parse_outputs()
print(json.dumps(outputs, indent=2))
