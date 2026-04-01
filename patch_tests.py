import re

with open("backend/tests/test_services/test_session_service.py", "r") as f:
    content = f.read()

content = content.replace("new_col = _FakeQuery(self._store, self._col, field, op, value, self._order_field)", "new_col = _FakeQuery(self._store, self._col, field, op, value, getattr(self, '_order_field', None))")

with open("backend/tests/test_services/test_session_service.py", "w") as f:
    f.write(content)
