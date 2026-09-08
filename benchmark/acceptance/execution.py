"""Portable execution identities and complete CI cohort validation."""
import copy
from .common import digest

GROUPS = {'release': {1, 5, 10, 11}, 'local': {2, 6, 7}, 'privacy': {3}, 'cloud': {4, 8}, 'quality': {9}}


def portable(value):
    if isinstance(value, list):
        return [portable(x) for x in value]
    if not isinstance(value, dict):
        return value
    # Content identity replaces only the location of an identified object.
    return {k: portable(v) for k, v in value.items()
            if not (k in {'path', 'uri'} and value.get('sha256'))}


def manifest(data):
    rows = []
    for case in data['cases']:
        group = next(g for g, requirements in GROUPS.items() if int(case['covers'][0][-2:]) in requirements)
        definition = portable({k: copy.deepcopy(case[k]) for k in
                               ['id', 'source', 'options', 'evaluation', 'facts', 'operation', 'covers', 'contract', 'retentionContract'] if k in case})
        checks = sorted(case['evaluation']['checks'], key=lambda c: c['id'])
        definition['evaluation']['checks'] = portable(checks)
        rows.append({'id': case['id'], 'group': group, 'sourceSha256': case['source']['sha256'],
                     'checks': portable(checks), 'definitionHash': digest(definition)})
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate manifest cases')
    for row in rows:
        if not row['checks'] or len({c['id'] for c in row['checks']}) != len(row['checks']):
            raise ValueError('Empty or duplicate manifest checks')
    return {'version': 1, 'cases': sorted(rows, key=lambda r: r['id'])}


def validate_group(envelope, questions, expected):
    group = envelope['group']
    rows = [r for r in expected['cases'] if r['group'] == group]
    results = envelope['results']
    if not rows or len(results) != len(rows) or {r['caseId'] for r in results} != {r['id'] for r in rows}:
        raise ValueError('Missing, extra or duplicate cases in CI group ' + group)
    by_id = {r['id']: r for r in rows}
    question_ids = []
    for result in results:
        row = by_id[result['caseId']]
        if result.get('inputSha256') != row['sourceSha256']:
            raise ValueError('CI source identity differs')
        checks = row['checks']; actual = result['assertions']
        if len(actual) != len(checks) or {a['id'] for a in actual} != {c['id'] for c in checks}:
            raise ValueError('Missing, extra or duplicate CI assertions')
        definitions = {c['id']: c for c in checks}
        for assertion in actual:
            check = definitions[assertion['id']]
            if any(portable(assertion.get(k)) != v for k, v in check.items()):
                raise ValueError('CI assertion definition differs from snapshot')
            if assertion.get('status') not in {'passed', 'failed', 'blocked', 'review'}:
                raise ValueError('Invalid assertion status')
        question_ids.extend(c['questionId'] for c in checks)
    if len(questions) != len(question_ids) or {q['questionId'] for q in questions} != set(question_ids):
        raise ValueError('CI question inventory differs')
