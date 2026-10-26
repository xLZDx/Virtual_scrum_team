import base64,pathlib,subprocess,tarfile
payload=pathlib.Path(r'D:\Temp\vst-s4-621ddc01-final.tar.gz').read_bytes()
remote=pathlib.Path(r'D:\Temp\vst-s4-621ddc01-wsl-atomic-r6.sh').read_text(encoding='utf-8')
p=subprocess.Popen(['wsl.exe','-d','Ubuntu-24.04','-u','root','--exec','/bin/bash','-c',remote],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
out,err=p.communicate(input=payload)
text=out.decode('utf-8','replace')
pathlib.Path(r'D:\Temp\vst-s4-621ddc01-wsl-r6-stdout.txt').write_text(text,encoding='utf-8')
pathlib.Path(r'D:\Temp\vst-s4-621ddc01-wsl-r6-stderr.txt').write_bytes(err)
print('WSL_EXIT='+str(p.returncode))
print('HOST_PAYLOAD_BYTES='+str(len(payload)))
print('HOST_PAYLOAD_SHA256='+__import__('hashlib').sha256(payload).hexdigest())
marker='ARTIFACTS_BASE64_BEGIN\n'; end='\nARTIFACTS_BASE64_END'
if marker in text and end in text:
    data=text.split(marker,1)[1].split(end,1)[0]
    raw=base64.b64decode(data)
    pathlib.Path(r'D:\Temp\vst-s4-621ddc01-wsl-r6-artifacts.tar.gz').write_bytes(raw)
    with tarfile.open(fileobj=__import__('io').BytesIO(raw),mode='r:gz') as tar:
        tar.extractall(path=r'D:\Temp\vst-s4-621ddc01-wsl-r6-artifacts',filter='data')
    print('ARTIFACT_TAR_BYTES='+str(len(raw)))
    print('ARTIFACT_TAR_SHA256='+__import__('hashlib').sha256(raw).hexdigest())
else: print('ARTIFACT_EXPORT=ABSENT')
print(text.split(marker,1)[0] if marker in text else text)
print('STDERR_BEGIN');print(err.decode('utf-8','replace'));print('STDERR_END')

