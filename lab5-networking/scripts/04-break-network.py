"""Apply one random policy fault. Restore from chart values after diagnosis."""
import copy
import json
import os
from pathlib import Path
import random
import subprocess
import time
import yaml

lab = Path(__file__).resolve().parents[1]
base = yaml.safe_load((lab/'charts/shop/values.yaml').read_text())
policies = copy.deepcopy(base['networkPolicy']['policies'])
by_name = {p['name']: p['spec'] for p in policies}
choice = random.randrange(3)
if choice == 0:
    by_name['client']['egress'][0]['ports'][0]['port'] = 8001
elif choice == 1:
    by_name['api']['ingress'][0]['from'][0]['podSelector']['matchLabels']['app'] = 'panda-client-typo'
else:
    # Keep DNS for other workloads, but exclude the operator terminal.
    by_name['dns']['podSelector'] = {'matchExpressions': [
        {'key': 'app', 'operator': 'NotIn', 'values': ['panda-client']}]}
folder = lab/'report/evidence'/time.strftime('fault-%Y%m%d-%H%M%S')
folder.mkdir(parents=True)
values = folder/'fault-values.yaml'
values.write_text(yaml.safe_dump({'networkPolicy': {'enabled': True, 'policies': policies}},sort_keys=False))
# Preserve the active release for later audit; do not print the selected fault.
kubeconfig = os.getenv('LAB5_KUBECONFIG', str(Path.home()/'.kube/lab5.yaml'))
helm = ['helm', '--kubeconfig', kubeconfig, '--kube-context', 'kind-lab5']
previous = subprocess.check_output(helm+['get','values','shop','-n','shop','-o','yaml'],text=True)
(folder/'values-before.yaml').write_text(previous)
subprocess.run(helm+['upgrade','shop',str(lab/'charts/shop'),'-n','shop','--reuse-values',
                    '-f',str(values),'--timeout','2m'],check=True)
print('One policy fault applied. Evidence directory:',folder)
print('Diagnose in Hubble before inspecting fault-values.yaml.')
