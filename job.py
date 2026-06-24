from uuid import uuid4
@@
 class Job:
     def __init__(self, time_str, instance, job_type=None, value=None, group_name=None, 
                  is_group=False, group_jobs=None, status="Đã hẹn"):
+        # stable unique id for UI mapping and persistence
+        self.uid = str(uuid4())
@@
     def to_dict(self):
         return {
+            'uid': getattr(self, 'uid', None),
             'time_str': self.time_str,
             'instance': self.instance,
             'job_type': self.job_type,
             'value': self.value,
             'group_name': self.group_name,
             'is_group': self.is_group,
             'group_jobs': [job.to_dict() for job in self.group_jobs] if self.group_jobs else [],
             'status': self.status,
             'current_child_index': self.current_child_index,
             'is_repeating': getattr(self, 'is_repeating', False),  # Bắt buộc phải có dòng này
             'repeat_interval': getattr(self, 'repeat_interval', 0)  # Bắt buộc phải có dòng này
         }
@@
     def from_dict(cls, data):
         job = cls(
             time_str=data['time_str'],
             instance=data['instance'],
             job_type=data.get('job_type'),
             value=data.get('value'),
             group_name=data.get('group_name'),
             is_group=data.get('is_group', False),
             group_jobs=[cls.from_dict(j) for j in data.get('group_jobs', [])],
             status=data.get('status', 'Đã hẹn')
         )
+        # preserve uid if present (migration support)
+        if data.get('uid'):
+            job.uid = data.get('uid')
@@
 def load_jobs():
@@
         with open(JOBS_FILE, 'r', encoding='utf-8') as f:
             saved_data = json.load(f)
             for item in saved_data:
-                job = Job.from_dict(item)
+                job = Job.from_dict(item)
                 jobs.append(job)
@@
 def save_jobs():
@@
-        saved_data = [job.to_dict() for job in jobs]
+        saved_data = [job.to_dict() for job in jobs]
*** End Patch
