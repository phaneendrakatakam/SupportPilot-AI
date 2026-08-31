from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    '.env.example',
    'requirements.txt',
    'app/main.py',
    'app/config.py',
    'app/agent/orchestrator.py',
    'app/agent/resolution.py',
    'app/agent/schemas.py',
    'app/api/health.py',
    'app/api/support.py',
    'app/api/debug.py',
    'app/db/models.py',
    'app/db/schema.py',
    'app/db/seed.py',
    'app/db/session.py',
    'app/tools/customer.py',
    'app/tools/subscription.py',
    'app/tools/payment.py',
    'app/tools/service_status.py',
    'app/tools/knowledge.py',
    'app/templates/index.html',
    'app/templates/debug.html',
    'app/static/app.js',
    'app/static/styles.css',
    'app/static/debug.js',
    'app/static/debug.css',
    'scripts/bootstrap.py',
    'scripts/embed_knowledge.py',
]


def main() -> None:
    missing = [
        item
        for item in REQUIRED_FILES
        if not (PROJECT_ROOT / item).is_file()
    ]

    test_count = 0

    for test_file in (PROJECT_ROOT / 'tests').rglob('test_*.py'):
        test_count += len(
            re.findall(
                r'^def test_',
                test_file.read_text(encoding='utf-8'),
                flags=re.MULTILINE,
            )
        )

    if missing:
        print('Missing required files:')
        for item in missing:
            print(f' - {item}')
        raise SystemExit(1)

    print('SupportPilot V2 project structure: OK')
    print(f'Automated tests discovered by structure check: {test_count}')


if __name__ == '__main__':
    main()
