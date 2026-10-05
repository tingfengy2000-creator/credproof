from pathlib import Path
import shutil,subprocess,sys,json,os
clean=Path(r'C:\Users\Public\credproof-enhanced-clean-dev11a'); consumer=clean/'consumer3'
if consumer.exists(): shutil.rmtree(consumer)
shutil.copytree(Path('examples/external/reusable-consumer-fixture'),consumer); shutil.rmtree(consumer/'tests/credproof-regression')
py=str(clean/'venv/Scripts/python.exe'); run=lambda args: subprocess.run([py,*args],cwd=consumer,text=True,capture_output=True)
first=run(['-m','credproof_safety','export-tests','--config','credproof.toml','--output','tests/credproof-regression'])
pytest=run(['-m','pytest','-q','tests/credproof-regression/test_credproof_safety.py',"--junitxml=.credproof/clean-junit.xml"])
report=list((consumer/'.credproof').glob('consumer-report-*.json'))
print(json.dumps({'export_returncode':first.returncode,'pytest_returncode':pytest.returncode,'stdout':pytest.stdout,'stderr':pytest.stderr,'reports':[p.name for p in report]},ensure_ascii=False))

