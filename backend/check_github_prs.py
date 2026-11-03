import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

import itertools
from allauth.socialaccount.models import SocialToken
from github import Github
from repos.models import Repository

token = SocialToken.objects.filter(account__provider='github').first()
gh = Github(token.token)
user = gh.get_user()
print('GitHub user:', user.login)
print()

all_repos = list(itertools.islice(user.get_repos(type='all', sort='updated'), 20))
print(f'Checking {len(all_repos)} most recently updated repos...')
print()

repos_with_prs = []
for r in all_repos:
    try:
        pr_count = r.get_pulls(state='all').totalCount
        print(f'  {r.full_name}: {pr_count} PRs, private={r.private}')
        if pr_count > 0:
            repos_with_prs.append((r.full_name, pr_count))
    except Exception as e:
        print(f'  {r.full_name}: error - {e}')

print()
print('=== Repos WITH pull requests ===')
for name, count in repos_with_prs:
    print(f'  {name}: {count} PRs')
