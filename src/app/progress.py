# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Status details for the UI.
"""
from mapreduce import model as mr_model
import pipeline


def get_status(pipeline_id):
  """Hack into the pipelines models to gather pipeline and mapreduce details."""

  status_dict = {
    'pipeline_id': pipeline_id,
  }
  status_tree = pipeline.get_status_tree(pipeline_id)
  if not status_tree:
    return status_dict
  for info in status_tree.get('pipelines', {}).itervalues():
    if info.get('classPath') == 'mapreduce.mapper_pipeline.MapperPipeline':
      status_dict['pipeline_status'] = info['status']
      if 'statusConsoleUrl' not in info:
        return status_dict
      mapreduce_id = (
          info['statusConsoleUrl'][info['statusConsoleUrl'].rfind('=')+1:])
      status_dict['mapreduce_id'] = mapreduce_id
      mr_job = mr_model.MapreduceState.get_by_key_name(mapreduce_id)
      if not mr_job:
        return status_dict
      counters = mr_job.counters_map.to_json().get('counters', {})
      counters = {key.replace('-', '_'): value
                  for key, value in counters.iteritems()}
      status_dict.update({
        'mapreduce_counters': counters,
        'mapreduce_active': mr_job.active,
        'mapreduce_result_status': mr_job.result_status,
      })
      return status_dict
  return status_dict
