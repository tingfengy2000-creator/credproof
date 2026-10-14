"""Local developer revisions and append-only decisions, independent of the LLM.

Project execution always delegates to check_project. No operation applies a
candidate to its original repository. Hashes are identities, not signatures.
"""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import uuid
import zipfile

from agent_pilot.output_format import receive_python_source
from .access_dependency import dependency_receipt
from .config import load_config
from .project import _copy_project, _digest_tree, check_project
from .project_bundle import export_project_bundle, _bind_validation_object, _files


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8', newline='\n') as target:
        json.dump(data, target, ensure_ascii=False, indent=2)
        target.write('\n')


class ReviewWorkspace:
    def __init__(self, data):
        self.root = Path(data)/'runs/human-review'
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, identifier):
        if not isinstance(identifier, str) or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('unknown_review_id')
        folder = self.root/identifier
        if folder.is_symlink() or not (folder/'meta.json').is_file():
            raise ValueError('unknown_review_id')
        return folder

    def list(self):
        rows = []
        for p in sorted(self.root.glob('*/meta.json')):
            if p.parent.is_symlink():
                continue
            meta = read(p)
            rows.append({'id': p.parent.name, 'project_id': meta['project_id'], 'label': meta['label'],
                         'kind': meta.get('kind', 'AI_HISTORY'), 'created_at': meta.get('created_at')})
        return rows

    @staticmethod
    def version(folder):
        versions = sorted((folder/'versions').glob('v*/version.json'))
        if not versions:
            raise ValueError('revision_material_missing')
        return versions[-1].parent, read(versions[-1])

    def open_method(self, method, origin_id):
        identifier = uuid.uuid4().hex
        folder = self.root/identifier
        folder.mkdir()
        export_project_bundle(method, folder/'baseline')
        baseline = read(folder/'baseline/report.json')
        project = folder/'versions/v000/project'
        project.parent.mkdir(parents=True)
        _copy_project(folder/'baseline/project', project)
        entry = load_config(project/'credproof.toml').entry.module.replace('.', '/')+'.py'
        save(project.parent/'version.json', {'id': 'v000', 'parent': None, 'source': 'AI_HISTORY',
             'origin_id': origin_id, 'created_at': now(), 'reason': '导入真实AI历史候选；未进行新推理',
             'entry_path': entry, 'code_sha256': sha((project/entry).read_bytes())})
        save(project.parent/'reports/imported.json', baseline['final_validation'])
        save(folder/'meta.json', {'id': identifier, 'project_id': baseline['project_id'],
             'origin_id': origin_id, 'label': 'AI候选与开发者修订', 'created_at': now(),
             'original_sha256': sha((folder/'baseline/original.py').read_bytes()),
             'source_candidate_sha256': sha((folder/'baseline/candidate.py').read_bytes()),
             'application_to_original': 'NOT_APPLIED'})
        return self.view(identifier)

    def open_project(self, project, origin_id, label):
        """Freeze one configured project as v000; no execution, no model output.

        The baseline uses the same layout as an imported AI history so every
        later revise/check/decide/export goes through the unchanged binding.
        ``original.py`` and ``candidate.py`` are both the imported entry: there
        is no AI candidate in this record and the view reports ``ai_code`` as
        ``None``.
        """
        from .access_dependency import dependency_receipt
        from .project_bundle import _files
        project = Path(project)
        if not isinstance(label, str) or not label.strip() or len(label) > 80:
            raise ValueError('project_label_required')
        if not isinstance(origin_id, str) or not origin_id or len(origin_id) > 80:
            raise ValueError('project_origin_required')
        identifier = uuid.uuid4().hex
        folder = self.root/identifier
        folder.mkdir()
        baseline = folder/'baseline'
        _copy_project(project, baseline/'project')
        cfg = load_config(baseline/'project/credproof.toml', project_root=baseline/'project')
        entry = cfg.entry.module.replace('.', '/')+'.py'
        if not cfg.matches_source(entry) or not cfg.matches_mutable(entry):
            raise ValueError('entry_outside_source_or_mutable_scope')
        if not (baseline/'project'/entry).is_file():
            raise ValueError('entry_file_missing')
        if any(not (baseline/'project'/name).exists() for name in cfg.tests):
            raise ValueError('required_tests_missing')
        entry_bytes = (baseline/'project'/entry).read_bytes()
        (baseline/'original.py').write_bytes(entry_bytes)
        (baseline/'candidate.py').write_bytes(entry_bytes)
        source = Path(__file__).resolve().parents[1]/'credproof_access'
        dependency = baseline/'dependencies/credproof_access'
        dependency.mkdir(parents=True)
        for name in dependency_receipt(source)['files']:
            (dependency/name).write_bytes((source/name).read_bytes())
        save(baseline/'access-dependency.json', {'identity': dependency_receipt(dependency),
             'policy_reconstruction': 'fresh runner derives directory/service semantics from credproof.toml'})
        save(baseline/'manifest.json', {'schema': 'credproof.project-review-baseline/v1',
             'files': _files(baseline), 'execution_performed': False})
        version = folder/'versions/v000'
        _copy_project(baseline/'project', version/'project')
        save(version/'version.json', {'id': 'v000', 'parent': None, 'source': 'PROJECT_IMPORT',
             'origin_id': origin_id, 'created_at': now(),
             'reason': '导入项目当前代码，配置与测试一并冻结',
             'entry_path': entry, 'code_sha256': sha((version/'project'/entry).read_bytes())})
        save(folder/'meta.json', {'id': identifier, 'kind': 'PROJECT', 'project_id': origin_id,
             'origin_id': origin_id, 'label': label.strip(), 'created_at': now(),
             'original_sha256': sha(entry_bytes), 'source_candidate_sha256': sha(entry_bytes),
             'application_to_original': 'NOT_APPLIED'})
        return self.view(identifier)

    def _report(self, version):
        files = sorted((version/'reports').glob('*.json'), key=lambda p: p.name)
        return files[-1] if files else None

    def _binding(self, folder, version, meta):
        # The imported snapshot is immutable too, not a moving comparison base.
        for name, digest in read(folder/'baseline/manifest.json')['files'].items():
            path = folder/'baseline'/name
            if not path.is_file() or path.is_symlink() or sha(path.read_bytes()) != digest:
                raise ValueError('baseline_material_missing_or_changed: '+name)
        project = version/'project'
        cfg = load_config(project/'credproof.toml')
        # Only the configured entry is mutable. Tests/config/dependencies are
        # inherited from the frozen import, not from browser-supplied data.
        entry = meta['entry_path']
        if not (project/entry).is_file() or sha((project/entry).read_bytes()) != meta['code_sha256']:
            raise ValueError('revision_source_changed')
        if any(p.is_symlink() or getattr(p, 'is_junction', lambda:False)() for p in project.rglob('*')):
            raise ValueError('linked_revision_material')
        current = {p.relative_to(project).as_posix(): sha(p.read_bytes()) for p in project.rglob('*') if p.is_file()}
        original_root = folder/'baseline/project'
        frozen = {p.relative_to(original_root).as_posix(): sha(p.read_bytes()) for p in original_root.rglob('*') if p.is_file()}
        if {k:v for k,v in current.items() if k != entry} != {k:v for k,v in frozen.items() if k != entry}:
            raise ValueError('immutable_rules_or_tests_changed')
        if sha((folder/'baseline/original.py').read_bytes()) != read(folder/'meta.json')['original_sha256']:
            raise ValueError('original_baseline_changed')
        dep = folder/'baseline/dependencies/credproof_access'
        stored = read(folder/'baseline/access-dependency.json')['identity']
        actual = dependency_receipt(dep)
        if any(stored.get(k) != v for k,v in actual.items()) or actual != dependency_receipt():
            raise ValueError('component_material_changed')
        if not cfg.matches_mutable(entry):
            raise ValueError('entry_not_mutable')
        return _digest_tree(project), dep

    def view(self, identifier):
        folder = self.folder(identifier)
        version, meta = self.version(folder)
        report_path = self._report(version)
        report = read(report_path) if report_path else None
        report_sha = sha(report_path.read_bytes()) if report_path else None
        reasons = []
        try:
            obj, _ = self._binding(folder, version, meta)
            applicable = bool(report and report.get('project_tree_sha256') == obj)
            if report:
                _bind_validation_object({'final_validation':report}, version/'project', (version/'project'/meta['entry_path']).read_bytes())
        except (ValueError, OSError, KeyError) as error:
            obj, applicable = None, False
            reasons.append(str(error))
        events = [read(p) for p in sorted((folder/'decisions').glob('*.json'))]
        latest = next((e for e in reversed(events) if e['version_id'] == meta['id']), None)
        decision_applicable = bool(latest and not reasons and latest['object_sha256'] == obj
                                   and latest['report_sha256'] == report_sha
                                   and (latest['decision'] != 'APPROVED' or applicable))
        state = latest['decision'] if decision_applicable else 'PENDING'
        source_path = version/'project'/meta['entry_path']
        code = source_path.read_text(encoding='utf8') if source_path.is_file() else ''
        meta_record = read(folder/'meta.json')
        is_project = meta_record.get('kind') == 'PROJECT'
        ai = (folder/'baseline/candidate.py').read_text(encoding='utf8')
        parent_code = ai if meta['id']=='v000' else (folder/'versions'/meta['parent']/'project'/meta['entry_path']).read_text(encoding='utf8')
        return {'id':identifier, 'meta':{**meta_record, 'kind':meta_record.get('kind','AI_HISTORY')}, 'version':meta,
                'original_code':(folder/'baseline/original.py').read_text(encoding='utf8'),
                'ai_code':None if is_project else ai, 'code':code, 'diff':''.join(difflib.unified_diff(parent_code.splitlines(True),code.splitlines(True),fromfile='parent.py',tofile='revision.py')),
                'object_sha256':obj,'report_sha256':report_sha,'report':report,
                'technical_verdict':report['verdict'] if applicable else 'UNKNOWN',
                'report_applicable':applicable,'material_reasons':reasons,
                'decision':state,'decision_applicable':decision_applicable,
                'decision_is_test':bool(latest and latest.get('test_operation')),
                'decisions':events,'application_to_original':'NOT_APPLIED',
                'versions':[read(p) for p in sorted((folder/'versions').glob('*/version.json'))]}

    def _expected(self, identifier, expected):
        state = self.view(identifier)
        if not isinstance(expected, dict) or set(expected) != {'version_id','object_sha256','report_sha256','decision_count'}:
            raise ValueError('expected_current_version_required')
        actual = {'version_id':state['version']['id'],'object_sha256':state['object_sha256'],
                  'report_sha256':state['report_sha256'],'decision_count':len(state['decisions'])}
        if expected != actual or state['material_reasons']:
            raise ValueError('stale_version_or_material_changed')
        return state

    def revise(self, identifier, expected, code, reason):
        state = self._expected(identifier, expected)
        if not isinstance(reason, str) or not reason.strip() or len(reason)>1000:
            raise ValueError('revision_reason_required')
        return self._append_version(identifier, state, code, reason, 'DEVELOPER_REVISION')

    def _append_version(self, identifier, state, code, reason, source_kind, provenance=None):
        source, receipt = receive_python_source(code)
        if source == state['code']:
            raise ValueError('NO_CHANGE')
        folder = self.folder(identifier)
        parent, parent_meta = self.version(folder)
        self._binding(folder, parent, parent_meta)
        version = folder/'versions'/('v%03d'%len(state['versions']))
        version.mkdir()
        _copy_project(parent/'project', version/'project')
        entry = version/'project'/parent_meta['entry_path']
        entry.write_text(source, encoding='utf8', newline='\n')
        save(version/'version.json', {'id':version.name,'parent':parent_meta['id'],
             'source':source_kind,'reason':reason,'created_at':now(),
             'entry_path':parent_meta['entry_path'],'code_sha256':sha(entry.read_bytes()), **(provenance or {})})
        save(version/'format-receipt.json', receipt)
        self._binding(folder, version, read(version/'version.json'))
        return self.view(identifier)

    def propose(self, identifier, expected):
        """One model proposal; new object UNKNOWN/PENDING, never auto-check/adopt."""
        from .proposal import generate_proposal
        state=self._expected(identifier, expected)
        if state['technical_verdict']!='FAIL' or not state['report_applicable']:
            raise ValueError('propose_requires_current_FAIL')
        folder=self.folder(identifier);version,meta=self.version(folder)
        self._binding(folder,version,meta)
        proposal_id=uuid.uuid4().hex
        result=generate_proposal(version/'project/credproof.toml',state['report'],folder/'proposals'/proposal_id)
        # Recheck after inference: a moving source/report cannot authorize a
        # new version, even if a caller bypasses the server's operation lock.
        self._expected(identifier, expected)
        public={k:v for k,v in result.items() if k in ('status','reason','model','strategy','model_requests',
                 'native_tool_calls','verifications','request_sha256','response_sha256','boundary_status')}
        if result.get('status')=='CANDIDATE' and result['code']==state['code']:
            public.update(status='NO_CANDIDATE',reason='NO_CHANGE')
        save(folder/'proposals'/proposal_id/'review-receipt.json',{'proposal_id':proposal_id,
             'source_version':meta['id'],'source_object_sha256':state['object_sha256'],
             'source_report_sha256':state['report_sha256'],**public})
        if public.get('status')!='CANDIDATE':
            return {**public,'status':'NO_CANDIDATE','review':self.view(identifier)}
        provenance={k:result[k] for k in ('model','request_sha256','response_sha256','strategy')}
        provenance['proposal_id']=proposal_id
        provenance['model_format']=result.get('format_receipt')
        view=self._append_version(identifier,state,result['code'],result['reason'],'AI_CANDIDATE',provenance)
        return {**public,'status':'CANDIDATE','review':view}

    def check(self, identifier, expected):
        self._expected(identifier, expected)
        folder = self.folder(identifier)
        version, meta = self.version(folder)
        obj, dependency = self._binding(folder, version, meta)
        output = version/'reports'/('z-'+now().replace(':','-')+'-'+uuid.uuid4().hex+'.json')
        output.parent.mkdir(exist_ok=True)
        report = check_project(version/'project/credproof.toml', output=output,
                               project_root=version/'project', access_dependency=dependency)
        if _digest_tree(version/'project') != obj:
            raise ValueError('object_changed_during_check')
        # Rechecking changes the referenced report; no decision is restored.
        return self.view(identifier)

    def decide(self, identifier, expected, decision, reason, *, test_operation=False):
        state = self._expected(identifier, expected)
        if decision not in ('NEEDS_CHANGES','REJECTED','APPROVED') or type(test_operation) is not bool:
            raise ValueError('invalid_decision')
        if not isinstance(reason,str) or not reason.strip() or len(reason)>1000:
            raise ValueError('decision_reason_required')
        if decision == 'APPROVED' and (state['technical_verdict'] != 'PASS' or not state['report_applicable']):
            raise ValueError('approval_requires_current_complete_PASS')
        folder = self.folder(identifier)
        version, meta = self.version(folder)
        binding = None
        if state['report_applicable']:
            binding = _bind_validation_object({'final_validation':state['report']},version/'project',(version/'project'/meta['entry_path']).read_bytes())
        self._expected(identifier, expected)
        save(folder/'decisions'/('%06d-'%len(state['decisions'])+uuid.uuid4().hex+'.json'),
             {'decision':decision,'version_id':meta['id'],'object_sha256':state['object_sha256'],
              'report_sha256':state['report_sha256'],'object_binding':binding,
              'original_sha256':state['meta']['original_sha256'],
              'component':dependency_receipt(folder/'baseline/dependencies/credproof_access'),
              'reason':reason,'at':now(),'operation_source':'local-review-interface',
              'reviewer':'approval-function-test' if test_operation else 'local-operator-unverified',
              'test_operation':test_operation,'trust':'local record; not strong identity, signature or certification'})
        return self.view(identifier)

    def export(self, identifier, expected, *, adopted=False):
        state = self._expected(identifier, expected)
        if type(adopted) is not bool:
            raise ValueError('invalid_export_kind')
        if adopted and (state['technical_verdict']!='PASS' or state['decision']!='APPROVED' or not state['decision_applicable']):
            raise ValueError('adopted_export_requires_current_PASS_and_approval')
        folder = self.folder(identifier)
        version, meta = self.version(folder)
        obj, _ = self._binding(folder, version, meta)
        dest = folder/'exports'/uuid.uuid4().hex
        dest.mkdir(parents=True)
        if state['report_applicable']:
            method = dest/'method'; method.mkdir()
            (method/'original.py').write_bytes((folder/'baseline/original.py').read_bytes())
            (method/'final-candidate.py').write_bytes((version/'project'/meta['entry_path']).read_bytes())
            save(method/'result.json', {'schema':'credproof.web-live-record/v1', 'project_id':state['meta']['project_id'],
                 'case_id':'developer-review','artifact_dir':str(version), 'final_validation':state['report'],
                 'execution_kind':meta['source'],'model':{'model_calls':0},'candidate_count':0,
                 'source_sha256':state['meta']['original_sha256'],'candidate_sha256':meta['code_sha256']})
            # The existing exporter expects artifact/candidate. A private copy
            # is re-bound to the recorded report before export, then checked again.
            _copy_project(version/'project', dest/'artifact/candidate')
            row=read(method/'result.json'); row['artifact_dir']=str(dest/'artifact')
            (method/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            export_project_bundle(method, dest/'bundle')
        else:
            # Unevaluated diagnostics do not invent a validation/tree binding.
            (dest/'bundle').mkdir()
            _copy_project(version/'project', dest/'bundle/project')
        bundle=dest/'bundle'
        is_project = state['meta']['kind'] == 'PROJECT'
        if not is_project:
            (bundle/'ai-candidate.py').write_bytes((folder/'baseline/candidate.py').read_bytes())
        save(bundle/'human-review.json', {'scope':'PROJECT_REVIEW' if is_project else 'AI_ASSISTED_HUMAN_REVIEW','kind':'ADOPTED_REPAIR' if adopted else 'DIAGNOSTIC_OR_PENDING_REPAIR',
             'original_sha256':state['meta']['original_sha256'],'source_candidate_sha256':state['meta']['source_candidate_sha256'],
             'version':meta,'technical_verdict':state['technical_verdict'],'report_sha256':state['report_sha256'],
             'decision':state['decision'],'decision_is_test':state['decision_is_test'],
             'decisions':state['decisions'],'application_to_original':'NOT_APPLIED',
             'applicability':'Only this baseline, candidate, configuration, tests and component. Apply manually after review.'})
        (bundle/'revision.diff').write_text(''.join(difflib.unified_diff(state['original_code'].splitlines(True),state['code'].splitlines(True),fromfile='baseline.py',tofile='revision.py')),encoding='utf8',newline='\n')
        (bundle/'NOTICE.md').write_text('# '+('采纳功能测试包' if adopted and state['decision_is_test'] else '已验证且已采纳修复包' if adopted else '诊断或待本人采纳材料')+'\n\n技术结果 '+state['technical_verdict']+'；人工状态 '+state['decision']+'。未应用原仓库。\n',encoding='utf8')
        if (bundle/'manifest.json').exists():
            manifest=read(bundle/'manifest.json');manifest['files']=_files(bundle)
            (bundle/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        if _digest_tree(version/'project')!=obj or self.view(identifier)['report_sha256']!=state['report_sha256']:
            raise ValueError('object_or_report_changed_during_export')
        archive=dest/'credproof-review.zip'
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as out:
            for p in sorted(bundle.rglob('*')):
                if p.is_file():out.write(p,p.relative_to(bundle).as_posix())
        return archive
