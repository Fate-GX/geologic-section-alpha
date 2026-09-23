"""Read-only exact-file check. Never upgrades publication or human approval."""
import hashlib
import json
from pathlib import Path


def verify(root):
    root=Path(root).resolve()
    manifest=json.loads((root/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    expected={};errors=[]
    for row in manifest['files']:
        name=row['path'];part=Path(name)
        if (part.is_absolute() or '..' in part.parts or ':' in name or '\\' in name
                or name.casefold() in expected):
            raise ValueError('UnsafeOrDuplicatePackagePath')
        expected[name.casefold()]=name
        path=root/part
        chain=(path,*[p for p in path.parents if p!=root and root in p.parents])
        if any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in chain):
            errors.append('LinkedFile:'+name);continue
        if not path.is_file():errors.append('Missing:'+name);continue
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            errors.append('Changed:'+name)
    actual=set()
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if {'.venv','.git','__pycache__'}.intersection(relative.parts):continue
        if relative.parts[0]=='results' and relative.as_posix()!='results/README.md':continue
        if relative.parts[:2]==('app','dwg'):continue
        if relative.parts[:4]==('app','research','geologic_dwg_generation','cache'):continue
        if path.is_file() and relative.as_posix()!='PACKAGE_MANIFEST.json':
            actual.add(relative.as_posix().casefold())
    errors.extend('Extra:'+name for name in sorted(actual-set(expected)))
    return {'passed':not errors,'errors':errors,'checkedFiles':len(expected),
            'publicationAuthorized':False}


if __name__=='__main__':
    result=verify(Path(__file__).resolve().parents[1])
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 2)
