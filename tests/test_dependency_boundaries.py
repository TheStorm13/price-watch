"""Guard the boundaries introduced by ARCH-03 against concrete storage imports."""
import ast
from importlib.util import resolve_name
from pathlib import Path
import unittest


class DependencyBoundariesTests(unittest.TestCase):
    def test_policies_consumers_and_routes_do_not_import_storage(self):
        root = Path(__file__).resolve().parents[1]
        for area in ('domain', 'application', 'ports', 'worker', 'api/routes'):
            for path in (root/'price_watch'/area).glob('*.py'):
                module = '.'.join(path.relative_to(root).with_suffix('').parts)
                package = module if path.name == '__init__.py' else module.rsplit('.', 1)[0]
                for node in ast.walk(ast.parse(path.read_text())):
                    imports = []
                    if isinstance(node, ast.Import):
                        imports = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        name = '.'*node.level + (node.module or '')
                        imports = [resolve_name(name, package) if node.level else name]
                    for name in imports:
                        with self.subTest(path=path.relative_to(root), dependency=name):
                            self.assertFalse(name.startswith(('price_watch.infrastructure', 'sqlalchemy')))
                            if area != 'api/routes':
                                self.assertFalse(name.startswith(('price_watch.api', 'fastapi', 'pydantic')))
