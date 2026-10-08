"""Compare frozen policy wording and saved responses without inference."""
from collections import Counter
from statistics import mean


def summarize(pairs):
    complete = [p for p in pairs if p['both_completed']]
    parsed = [p for p in pairs if p['both_parsed']]
    return {
        'planned_pairs': len(pairs),
        'same_wording': sum(p['same_wording'] for p in pairs),
        'same_prompt': sum(p['same_prompt'] for p in pairs),
        'both_completed': len(complete),
        'both_parsed': len(parsed),
        'common_quartets': sum(p['common_quartet'] for p in pairs),
        'same_raw_response': sum(p['same_raw_response'] for p in complete),
        'same_native_lab': sum(p['same_native_lab'] for p in parsed),
        'same_displayed_hex': sum(p['same_displayed_hex'] for p in parsed),
        'identical_prompt_different_native_lab': sum(p['same_prompt'] and not p['same_native_lab'] for p in parsed),
        'exact_error_ties': sum(p['error_delta'] == 0 for p in parsed),
        'tolerance_error_ties': sum(abs(p['error_delta']) <= 0.01 for p in parsed),
        'wins': sum(p['error_delta'] < -0.01 for p in parsed),
        'losses': sum(p['error_delta'] > 0.01 for p in parsed),
        'mean_error_delta': mean(p['error_delta'] for p in parsed) if parsed else None,
        'phrase_transitions': dict(Counter(p['wording_transition'] for p in pairs)),
    }


def analyze(tasks, rows):
    grouped = {}
    for task in tasks:
        grouped.setdefault(task['case_id'], {})[task['arm']] = task
    pairs = []
    for key, g in sorted(grouped.items()):
        if 'unfitted' not in g or 'calibrated' not in g:
            raise ValueError('Identity audit requires a four-arm confirmation')
        a, b = g['unfitted'], g['calibrated']
        ra, rb = rows.get(a['condition_id']), rows.get(b['condition_id'])
        completed = ra is not None and rb is not None
        good = completed and ra['parse_ok'] and rb['parse_ok']
        quartet = all(t['status'] == 'generate' and t['condition_id'] in rows and rows[t['condition_id']]['parse_ok'] for t in g.values()) and len(g) == 4
        pairs.append({
            'case_id': key, 'base_id': a['base_id'], 'direction': a['direction'],
            'requested_distance': a['requested_distance'],
            'wording_transition': f"{a['selected_wording']} -> {b['selected_wording']}",
            'same_wording': a['selected_wording'] == b['selected_wording'],
            'same_prompt': a['prompt'] is not None and a['prompt'] == b['prompt'],
            'both_completed': completed, 'both_parsed': good, 'common_quartet': quartet,
            'same_raw_response': completed and ra['raw_response'] == rb['raw_response'],
            'same_native_lab': good and ra['native_lab'] == rb['native_lab'],
            'same_displayed_hex': good and ra['displayed_state']['hex'] == rb['displayed_state']['hex'],
            'error_delta': rb['metrics']['projected_target_error'] - ra['metrics']['projected_target_error'] if good else None,
        })
    common = [p for p in pairs if p['common_quartet']]
    result = {'all_pairs': summarize(pairs), 'common_quartets': summarize(common), 'by_direction_distance': [], 'by_prompt_identity': [], 'pairs': pairs}
    for direction, distance in sorted({(p['direction'], p['requested_distance']) for p in pairs}):
        selected = [p for p in pairs if p['direction'] == direction and p['requested_distance'] == distance]
        result['by_direction_distance'].append({'direction': direction, 'requested_distance': distance, **summarize(selected)})
    for same in (True, False):
        result['by_prompt_identity'].append({'same_prompt': same, **summarize([p for p in common if p['same_prompt'] == same])})
    return result


def report(result, run_id):
    lines = [f'# Saved magnitude policy identity: {run_id}', '', 'CPU-only audit; no fitting, repair, or model calls.', '', 'Counts below distinguish planned policy identity from parsed response identity.', '', '| Direction / distance | Planned | Same wording | Same prompt | Both parsed | Same LAB | Same HEX | Exact error ties | Prompt-equal LAB mismatches |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in [{'direction':'ALL', 'requested_distance':'', **result['all_pairs']}, *result['by_direction_distance']]:
        lines.append(f"| {r['direction']} / {r['requested_distance']} | {r['planned_pairs']} | {r['same_wording']} | {r['same_prompt']} | {r['both_parsed']} | {r['same_native_lab']} | {r['same_displayed_hex']} | {r['exact_error_ties']} | {r['identical_prompt_different_native_lab']} |")
    lines += ['', '## Common-quartet effects by prompt identity', '', '| Same prompt | Cases | Mean calibrated − unfitted ΔE | Wins / ties / losses |', '|---|---:|---:|---|']
    for r in result['by_prompt_identity']:
        effect = f"{r['mean_error_delta']:.6f}" if r['mean_error_delta'] is not None else 'n/a'
        lines.append(f"| {r['same_prompt']} | {r['both_parsed']} | {effect} | {r['wins']} / {r['tolerance_error_ties']} / {r['losses']} |")
    lines += ['', '## Phrase transitions (all planned pairs)', '', '| Direction / distance | Unfitted → calibrated | N |', '|---|---|---:|']
    for r in result['by_direction_distance']:
        for transition, n in sorted(r['phrase_transitions'].items()):
            lines.append(f"| {r['direction']} / {r['requested_distance']} | {transition} | {n} |")
    lines += ['', '## Limits', '', 'This checks literal prompt and response identity, not semantic equivalence. Equal target errors can occur for different colors. Prompt-identical greedy generations are repeated executions of the same instruction, not independent controller interventions or proof of backend determinism. Failed and pending responses are not assigned colors. Prompt-identity groups are post hoc diagnostics, not randomized subgroups or causal effects. No subgroup significance test or new confidence interval is performed. The primary cohort remains all common parsed quartets. All pair details remain in metrics/magnitude_identity.json; original plans, controllers, checkpoints and reports are preserved.']
    return '\n'.join(lines) + '\n'
