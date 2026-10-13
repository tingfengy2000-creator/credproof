"""Verify downloaded hosted artifacts, preserve text receipts, derive C results.

Operator tool only. Does not execute projects, models, Docker or network calls.
Downloads are original GitHub ZIP bytes; public text was already field-redacted
by the runner. This collector never changes a verdict or candidate.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def sha(value):return hashlib.sha256(value).hexdigest()
def load(path):return json.loads(path.read_text('utf8'))
def save(path,value):path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())


def main():
    p=argparse.ArgumentParser();p.add_argument('--downloads',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    metadata=load(a.output/'artifact-receipts.json');rows=[];receipts=[]
    for meta in metadata:
        label,job=meta['label'],meta['job'];archive=a.downloads/f'ci-c-final-{label}-{job}.zip'
        raw=archive.read_bytes()
        if sha(raw)!=meta['sha256'] or len(raw)!=meta['bytes']:raise ValueError('GitHub ZIP digest mismatch')
        out=a.output/'runs'/label/job;out.mkdir(parents=True,exist_ok=True)
        copied={}
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name=PurePosixPath(info.filename)
                if name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe artifact path')
                if info.is_dir() or 'project' in name.parts or 'mismatched-runtime' in name.parts:continue
                if name.suffix not in ('.json','.txt','.xml','.md','.sarif','.profile'):continue
                data=z.read(info)
                if re.search(rb'CP_LAB_[A-F0-9]{6,}',data):raise ValueError('Unredacted synthetic credential')
                path=out/str(name);path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists() and path.read_bytes()!=data:raise ValueError('Refuse to overwrite different public evidence')
                path.write_bytes(data)
                copied[str(name)]={'bytes':len(data),'sha256':sha(data)}
        report=load(out/'target-0/report.json');commands=load(out/'commands.json')
        anchors=load(out/'anchors-results/summary.json');doctor=load(out/'doctor.json')
        formats=load(out/'formats-scan.json');identity=load(out/'identity.json')
        observation=report['execution']['pytest_observation']
        expected='FAIL' if label=='vulnerable' else 'PASS'
        checks=report['required_checks'];failed=[k for k,v in checks.items() if v is False]
        assert report['verdict']==expected
        assert checks['required_pytest_tests'] and observation['required_tests_passed']
        assert observation['required_case_count']==2 and observation['passed']==2
        assert anchors['matched']==anchors['expected_count']==16 and all(x['matches'] for x in anchors['rows'])
        assert doctor['ready'] and all(x is True for x in doctor['checks'].values())
        assert formats['status']=='COMPLETED' and formats['sensitive_hits']==0
        assert failed==(['required_entry_scenarios','no_forbidden_service_receipt','no_unauthorized_connection'] if label=='vulnerable' else [])
        assert next(x for x in commands if x['name']=='check-0')['exit_code']==(2 if label=='vulnerable' else 0)
        assert all(x['matches'] for x in commands if x['name']!='check-0')
        sarif=load(out/'target-0/report.sarif')
        assert len(sarif['runs'][0]['results'])==(3 if label=='vulnerable' else 0)
        assert all('region' not in loc['physicalLocation'] for r in sarif['runs'][0]['results'] for loc in r.get('locations',[]))
        row={'control':label,'environment':job,'run_id':meta['run_id'],'pr_head_sha':meta['head_sha'],
            'actual_checkout_sha':identity['source_commit'],'verdict':report['verdict'],
            'check_exit_code':2 if label=='vulnerable' else 0,'business_tests':2,
            'business_required_passed':True,'entry_scenarios':len(report['execution']['entry_scenarios']),
            'failed_checks':failed,'anchors_matched':anchors['matched'],
            'doctor_ready':True,'sandbox_apparmor_profile':doctor['sandbox_apparmor_profile'],
            'formats_scan_completed':True,'formats_sensitive_hits':0,'model_calls':0}
        if job=='container':
            scan=load(out/'image-scan.json');blocked=load(out/'default-blocked/report.json')
            assert scan['status']=='COMPLETED' and scan['sensitive_hits']==0 and scan['files_scanned']>5000
            assert next(x for x in commands if x['name']=='default-doctor')['exit_code']==4
            assert next(x for x in commands if x['name']=='default-check')['exit_code']==3
            assert not load(out/'default-blocked/doctor.json')['ready'] and blocked['verdict']=='UNKNOWN'
            row.update(image_scan_completed=True,image_sensitive_hits=0,image_files=scan['files_scanned'],
                image_bytes=scan['bytes_scanned'],reviewed_pattern_matches=len(scan['reviewed_exceptions']),
                default_doctor_exit=4,default_check_exit=3,default_check_verdict='UNKNOWN')
            text=(out/'build-receipt/stdout.txt').read_text('utf8')
            build,end=json.JSONDecoder().raw_decode(text)
            source,rootfs=[line.strip() for line in text[end:].splitlines() if line.strip()]
            build.update(source_commit=source,rootfs_manifest_sha256=rootfs,
                base_image=load(out/'base-image.json'),source_epoch=315532800)
            cert=re.search(r'Setting up ca-certificates \(([^)]+)\)',(out/'build/stderr.txt').read_text('utf8'))
            if cert:build['ca_certificates_version_from_build_log']=cert.group(1)
            save(out/'build-receipt.json',build)
        rows.append(row)
        receipts.append({'control':label,'job':job,'zip_sha256':sha(raw),'zip_bytes':len(raw),
            'public_files':copied,'omitted':'Copied project files and mismatch sentinel: frozen sources linked separately; no runtime/rootfs/wheel bytes published.'})
    save(a.output/'results.json',{'kind':'HOSTED_UBUNTU_24_04_C_ACCEPTANCE','model_calls':0,
        'program_source_commit':'466534c79eacf8dc9e59d267c9ee5e614b0f4a0f',
        'anchors_commit':'a5b51e303315dd2dd3f4671d7a771fb9afab0310','rows':rows})
    save(a.output/'collection-receipt.json',receipts)
    print(json.dumps({'rows':len(rows),'verified':True,'model_calls':0}))


if __name__=='__main__':main()
