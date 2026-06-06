from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any
API_URL = 'https://api.linear.app/graphql'

def _get_key() -> str:
    key = os.environ.get('LINEAR_API_KEY', '').strip()
    if not key:
        sys.stderr.write('ERROR: LINEAR_API_KEY not set.\nCreate one at https://linear.app/settings/api and export it,\nor add `LINEAR_API_KEY=lin_api_...` to ~/.hermes/.env\n')
        sys.exit(2)
    return key

def gql(query: str, variables: dict[str, Any] | None=None) -> dict[str, Any]:
    key = _get_key()
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(API_URL, data=data, headers={'Content-Type': 'application/json', 'Authorization': key, 'User-Agent': 'hermes-agent-linear-skill/1.0'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        sys.stderr.write(f'HTTP {e.code}: {e.read().decode('utf-8', 'replace')}\n')
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f'Network error: {e}\n')
        sys.exit(1)
    result = json.loads(body)
    if 'errors' in result and result['errors']:
        sys.stderr.write(f'GraphQL errors: {json.dumps(result['errors'], indent=2)}\n')
        if not result.get('data'):
            sys.exit(1)
    return result.get('data', {}) or {}

def emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))

def cmd_whoami(_args: argparse.Namespace) -> None:
    q = 'query { viewer { id name email displayName } }'
    emit(gql(q).get('viewer'))

def cmd_list_teams(_args: argparse.Namespace) -> None:
    q = 'query { teams(first: 100) { nodes { id key name description } } }'
    emit(gql(q).get('teams', {}).get('nodes', []))

def _resolve_team_id(key_or_name: str) -> str | None:
    q = 'query { teams(first: 100) { nodes { id key name } } }'
    teams = gql(q).get('teams', {}).get('nodes', [])
    kl = key_or_name.lower()
    for t in teams:
        if t['key'].lower() == kl or t['name'].lower() == kl:
            return t['id']
    return None

def cmd_list_projects(args: argparse.Namespace) -> None:
    if args.team:
        tid = _resolve_team_id(args.team)
        if not tid:
            sys.stderr.write(f'Team not found: {args.team}\n')
            sys.exit(1)
        q = 'query($id: String!) {\n          team(id: $id) { projects(first: 100) { nodes { id name description state } } }\n        }'
        data = gql(q, {'id': tid})
        emit(data.get('team', {}).get('projects', {}).get('nodes', []))
    else:
        q = 'query { projects(first: 100) { nodes { id name description state } } }'
        emit(gql(q).get('projects', {}).get('nodes', []))

def cmd_list_states(args: argparse.Namespace) -> None:
    if args.team:
        tid = _resolve_team_id(args.team)
        if not tid:
            sys.stderr.write(f'Team not found: {args.team}\n')
            sys.exit(1)
        q = 'query($id: String!) {\n          team(id: $id) { states(first: 100) { nodes { id name type color } } }\n        }'
        emit(gql(q, {'id': tid}).get('team', {}).get('states', {}).get('nodes', []))
    else:
        q = 'query { workflowStates(first: 200) { nodes { id name type team { key } } } }'
        emit(gql(q).get('workflowStates', {}).get('nodes', []))

def cmd_list_issues(args: argparse.Namespace) -> None:
    filt: dict[str, Any] = {}
    if args.team:
        filt['team'] = {'key': {'eq': args.team}}
    if args.status:
        filt['state'] = {'name': {'eq': args.status}}
    if args.assignee:
        filt['assignee'] = {'name': {'eq': args.assignee}}
    if args.label:
        filt['labels'] = {'name': {'eq': args.label}}
    q = 'query($filter: IssueFilter, $first: Int!) {\n      issues(filter: $filter, first: $first, orderBy: updatedAt) {\n        nodes {\n          id identifier title\n          state { name } priority\n          assignee { name }\n          team { key }\n          updatedAt url\n        }\n      }\n    }'
    data = gql(q, {'filter': filt or None, 'first': args.limit})
    emit(data.get('issues', {}).get('nodes', []))

def cmd_get_issue(args: argparse.Namespace) -> None:
    q = 'query($id: String!) {\n      issue(id: $id) {\n        id identifier title description\n        state { name type }\n        priority priorityLabel\n        assignee { name email }\n        creator { name }\n        team { key name }\n        project { name }\n        labels { nodes { name } }\n        parent { identifier title }\n        children { nodes { identifier title state { name } } }\n        comments { nodes { user { name } body createdAt } }\n        createdAt updatedAt url\n      }\n    }'
    emit(gql(q, {'id': args.identifier}).get('issue'))

def cmd_search_issues(args: argparse.Namespace) -> None:
    q = 'query($term: String!, $first: Int!) {\n      searchIssues(term: $term, first: $first) {\n        nodes { id identifier title state { name } url }\n      }\n    }'
    emit(gql(q, {'term': args.query, 'first': args.limit}).get('searchIssues', {}).get('nodes', []))

def cmd_create_issue(args: argparse.Namespace) -> None:
    tid = _resolve_team_id(args.team)
    if not tid:
        sys.stderr.write(f'Team not found: {args.team}\n')
        sys.exit(1)
    inp: dict[str, Any] = {'title': args.title, 'teamId': tid}
    if args.description:
        inp['description'] = args.description
    if args.priority is not None:
        inp['priority'] = args.priority
    if args.parent:
        inp['parentId'] = args.parent
    q = 'mutation($input: IssueCreateInput!) {\n      issueCreate(input: $input) {\n        success issue { id identifier title url }\n      }\n    }'
    emit(gql(q, {'input': inp}).get('issueCreate'))

def cmd_update_issue(args: argparse.Namespace) -> None:
    inp: dict[str, Any] = {}
    if args.title:
        inp['title'] = args.title
    if args.description:
        inp['description'] = args.description
    if args.priority is not None:
        inp['priority'] = args.priority
    if not inp:
        sys.stderr.write('No update fields provided.\n')
        sys.exit(1)
    q = 'mutation($id: String!, $input: IssueUpdateInput!) {\n      issueUpdate(id: $id, input: $input) {\n        success issue { identifier title url }\n      }\n    }'
    emit(gql(q, {'id': args.identifier, 'input': inp}).get('issueUpdate'))

def cmd_update_status(args: argparse.Namespace) -> None:
    get_q = 'query($id: String!) {\n      issue(id: $id) { team { id states(first: 100) { nodes { id name } } } }\n    }'
    issue = gql(get_q, {'id': args.identifier}).get('issue')
    if not issue:
        sys.stderr.write(f'Issue not found: {args.identifier}\n')
        sys.exit(1)
    sl = args.state.lower()
    match = next((s for s in issue['team']['states']['nodes'] if s['name'].lower() == sl), None)
    if not match:
        sys.stderr.write(f"State '{args.state}' not found. Available: {[s['name'] for s in issue['team']['states']['nodes']]}\n")
        sys.exit(1)
    q = 'mutation($id: String!, $stateId: String!) {\n      issueUpdate(id: $id, input: { stateId: $stateId }) {\n        success issue { identifier state { name } url }\n      }\n    }'
    emit(gql(q, {'id': args.identifier, 'stateId': match['id']}).get('issueUpdate'))

def cmd_add_comment(args: argparse.Namespace) -> None:
    q = 'mutation($input: CommentCreateInput!) {\n      commentCreate(input: $input) {\n        success comment { id body createdAt }\n      }\n    }'
    emit(gql(q, {'input': {'issueId': args.identifier, 'body': args.body}}).get('commentCreate'))

def cmd_list_documents(args: argparse.Namespace) -> None:
    q = 'query($first: Int!) {\n      documents(first: $first, orderBy: updatedAt) {\n        nodes { id title slugId updatedAt url project { name } creator { name } }\n      }\n    }'
    emit(gql(q, {'first': args.limit}).get('documents', {}).get('nodes', []))

def cmd_get_document(args: argparse.Namespace) -> None:
    ref = args.ref
    is_uuid = len(ref) == 36 and ref.count('-') == 4
    if is_uuid:
        q = 'query($id: String!) {\n          document(id: $id) {\n            id title content contentState slugId\n            createdAt updatedAt url\n            creator { name } project { name }\n          }\n        }'
        emit(gql(q, {'id': ref}).get('document'))
    else:
        q = 'query($slug: String!) {\n          documents(filter: { slugId: { eq: $slug } }, first: 1) {\n            nodes {\n              id title content contentState slugId\n              createdAt updatedAt url\n              creator { name } project { name }\n            }\n          }\n        }'
        nodes = gql(q, {'slug': ref}).get('documents', {}).get('nodes', [])
        emit(nodes[0] if nodes else None)

def cmd_search_documents(args: argparse.Namespace) -> None:
    q = 'query($term: String!, $first: Int!) {\n      documents(filter: { title: { containsIgnoreCase: $term } }, first: $first) {\n        nodes { id title slugId url updatedAt }\n      }\n    }'
    emit(gql(q, {'term': args.query, 'first': args.limit}).get('documents', {}).get('nodes', []))

def cmd_raw(args: argparse.Namespace) -> None:
    variables = json.loads(args.vars) if args.vars else None
    emit(gql(args.query, variables))

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='linear_api.py', description='Linear GraphQL CLI')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('whoami').set_defaults(func=cmd_whoami)
    sub.add_parser('list-teams').set_defaults(func=cmd_list_teams)
    lp = sub.add_parser('list-projects')
    lp.add_argument('--team')
    lp.set_defaults(func=cmd_list_projects)
    ls = sub.add_parser('list-states')
    ls.add_argument('--team')
    ls.set_defaults(func=cmd_list_states)
    li = sub.add_parser('list-issues')
    li.add_argument('--team')
    li.add_argument('--status')
    li.add_argument('--assignee')
    li.add_argument('--label')
    li.add_argument('--limit', type=int, default=25)
    li.set_defaults(func=cmd_list_issues)
    gi = sub.add_parser('get-issue')
    gi.add_argument('identifier')
    gi.set_defaults(func=cmd_get_issue)
    si = sub.add_parser('search-issues')
    si.add_argument('query')
    si.add_argument('--limit', type=int, default=25)
    si.set_defaults(func=cmd_search_issues)
    ci = sub.add_parser('create-issue')
    ci.add_argument('--title', required=True)
    ci.add_argument('--team', required=True)
    ci.add_argument('--description')
    ci.add_argument('--priority', type=int, choices=[0, 1, 2, 3, 4])
    ci.add_argument('--label')
    ci.add_argument('--assignee')
    ci.add_argument('--parent')
    ci.set_defaults(func=cmd_create_issue)
    ui = sub.add_parser('update-issue')
    ui.add_argument('identifier')
    ui.add_argument('--title')
    ui.add_argument('--description')
    ui.add_argument('--priority', type=int, choices=[0, 1, 2, 3, 4])
    ui.set_defaults(func=cmd_update_issue)
    us = sub.add_parser('update-status')
    us.add_argument('identifier')
    us.add_argument('state')
    us.set_defaults(func=cmd_update_status)
    ac = sub.add_parser('add-comment')
    ac.add_argument('identifier')
    ac.add_argument('body')
    ac.set_defaults(func=cmd_add_comment)
    ld = sub.add_parser('list-documents')
    ld.add_argument('--limit', type=int, default=50)
    ld.set_defaults(func=cmd_list_documents)
    gd = sub.add_parser('get-document')
    gd.add_argument('ref', help='slugId (hex suffix from URL) or full UUID')
    gd.set_defaults(func=cmd_get_document)
    sd = sub.add_parser('search-documents')
    sd.add_argument('query')
    sd.add_argument('--limit', type=int, default=25)
    sd.set_defaults(func=cmd_search_documents)
    r = sub.add_parser('raw')
    r.add_argument('query')
    r.add_argument('--vars', help='JSON string of variables')
    r.set_defaults(func=cmd_raw)
    return p

def main(argv: list[str] | None=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
if __name__ == '__main__':
    main()
