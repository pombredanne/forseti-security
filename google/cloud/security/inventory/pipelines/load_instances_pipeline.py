# Copyright 2017 The Forseti Security Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pipeline to load compute instances into Inventory.

This pipeline depends on the LoadProjectsPipeline.
"""

from google.cloud.security.common.data_access import project_dao as proj_dao
from google.cloud.security.common.util import log_util
from google.cloud.security.common.util import parser
from google.cloud.security.inventory.pipelines import base_pipeline

LOGGER = log_util.get_logger(__name__)


class LoadInstancesPipeline(base_pipeline.BasePipeline):
    """Load compute instances for all projects."""

    RESOURCE_NAME = 'instances'

    def _transform(self, resource_from_api):
        """Create an iterator of instances to load into database.

        Args:
            resource_from_api (dict): A dict of instances, keyed by
                project id, from GCP API.

        Yields:
            dict: Instance properties.
        """
        for (project_id, instances) in resource_from_api.iteritems():
            for instance in instances:
                yield {'project_id': project_id,
                       'id': instance.get('id'),
                       'creation_timestamp': parser.format_timestamp(
                           instance.get('creationTimestamp'),
                           self.MYSQL_DATETIME_FORMAT),
                       'name': instance.get('name'),
                       'description': instance.get('description'),
                       'can_ip_forward': self._to_bool(
                           instance.get('canIpForward', 0)),
                       'cpu_platform': instance.get('cpuPlatform'),
                       'disks': parser.json_stringify(
                           instance.get('disks', [])),
                       'machine_type': instance.get('machineType'),
                       'metadata': parser.json_stringify(
                           instance.get('metadata', {})),
                       'network_interfaces': parser.json_stringify(
                           instance.get('networkInterfaces', [])),
                       'scheduling': parser.json_stringify(
                           instance.get('scheduling', {})),
                       'service_accounts': parser.json_stringify(
                           instance.get('serviceAccounts', [])),
                       'status': instance.get('status'),
                       'status_message': instance.get('statusMessage'),
                       'tags': parser.json_stringify(instance.get('tags')),
                       'zone': instance.get('zone'),
                       'raw_instance': parser.json_stringify(instance)}

    def _retrieve(self):
        """Retrieve instances from GCP.

        Get all the projects in the current snapshot and retrieve the
        compute instances for each.

        Returns:
            dict: A map of projects with their instances (list):
            {project_id: [instances]}
        """
        projects = (proj_dao
                    .ProjectDao(self.global_configs)
                    .get_projects(self.cycle_timestamp))
        instances = {}
        for project in projects:
            project_instances = self.safe_api_call('get_instances',
                                                   project.id)
            if project_instances:
                instances[project.id] = project_instances
        return instances

    def run(self):
        """Run the pipeline."""
        instances = self._retrieve()
        loadable_instances = self._transform(instances)
        self._load(self.RESOURCE_NAME, loadable_instances)
        self._get_loaded_count()
