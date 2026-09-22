import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTING_DOCS = [ROOT / "SKILL.md", ROOT / "references" / "workflow-routing.md"]
RESOURCE_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])((?:references|scripts|assets)/[A-Za-z0-9_./-]+\.(?:md|py|csv|json|ya?ml))")


class SkillRoutingTests(unittest.TestCase):
    def test_advanced_routes_are_progressively_disclosed(self):
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/workflow-routing.md", skill_text)
        self.assertLess(len(skill_text), 10000)

    def test_routed_skill_resources_exist(self):
        missing = []
        for document in ROUTING_DOCS:
            text = document.read_text(encoding="utf-8")
            for resource in sorted(set(RESOURCE_PATTERN.findall(text))):
                if not (ROOT / resource).is_file():
                    missing.append(f"{document.relative_to(ROOT)} -> {resource}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
