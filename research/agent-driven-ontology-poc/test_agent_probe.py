"""Protocol unit tests using scripted responses. Never scored as model trials."""
from pathlib import Path
import json
import os
import unittest
from historical_inventory import FIXTURE, load_apis, normalize
from graph_views import Views
from agent_probe import episode, score, LocalModel


class AgentProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.getenv('SR_API_EXTRACT')
        cls.view = Views(*normalize(load_apis(Path(path) if path else FIXTURE, extracted=bool(path))))
        cls.tasks = json.loads(Path(__file__).with_name('graph-agent-dev-tasks.json').read_text())

    def test_task_rubric_schema_grounding(self):
        fields = {(self.view.routes[rid]['tool'], tuple(f['path'])) for rid, f in self.view.fields.values()}
        self.assertEqual(len(self.tasks), 12)
        for task in self.tasks:
            for need in task['needs']:
                for alt in need:
                    self.assertTrue({(alt['tool'], tuple(p)) for p in alt['paths']} <= fields)

    def test_scripted_actions_not_actual_model(self):
        task = self.tasks[2]
        found = next(h for h in self.view.find('is-referenced-by-count')['fieldHits'] if h['tool'] == 'crossref')
        final = {'action': 'final', 'status': 'select', 'selections': [{'route': found['route'], 'fields': [found['field']]}]}
        actions = iter([{'action': 'find', 'query': 'is-referenced-by-count'}, {'action': 'inspect', 'routes': [found['route']]}, final])
        def scripted(messages):
            self.assertNotIn('"needs"', messages[1]['content'])
            return {'choices': [{'message': {'content': json.dumps(next(actions))}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}
        row = episode(self.view, task, 'D-graph-browse', scripted)
        self.assertTrue(row['score']['success'])
        self.assertEqual(row['usage'], {'prompt_tokens': 300, 'completion_tokens': 60})
        row = episode(self.view, task, 'C-flat-browse', lambda _: {'choices': [{'message': {'content': json.dumps(final)}}]})
        self.assertFalse(row['score']['success'])
        self.assertIn('not inspected', row['error'])

    def test_unsupported_and_ambiguous(self):
        self.assertTrue(score(self.view, self.tasks[8], {'action': 'final', 'status': 'unavailable', 'selections': []})['success'])
        self.assertFalse(score(self.view, self.tasks[10], {'action': 'final', 'status': 'unavailable', 'selections': []})['success'])

    def test_model_endpoint_scope(self):
        for url in ['https://api.example.com/v1', 'http://example.com/v1', 'http://user:pass@localhost/v1', 'http://localhost/v1?key=abc']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                LocalModel(url, 'example')


if __name__ == '__main__':
    unittest.main()
