"""Deterministic field-level diff for normalized manifests."""
def diff(expected,actual):
 out=[]
 def walk(a,b,path=''):
  if isinstance(a,dict) and isinstance(b,dict):
   for k in sorted(set(a)|set(b)):
    p=f'{path}.{k}' if path else k
    if k not in a: out.append({'field_path':p,'expected':None,'actual':b[k],'change_type':'ADDED'})
    elif k not in b: out.append({'field_path':p,'expected':a[k],'actual':None,'change_type':'REMOVED'})
    else: walk(a[k],b[k],p)
  elif isinstance(a,list) and isinstance(b,list):
   for i in range(max(len(a),len(b))):
    p=f'{path}[{i}]'
    if i>=len(a): out.append({'field_path':p,'expected':None,'actual':b[i],'change_type':'ADDED'})
    elif i>=len(b): out.append({'field_path':p,'expected':a[i],'actual':None,'change_type':'REMOVED'})
    else: walk(a[i],b[i],p)
  elif a!=b: out.append({'field_path':path,'expected':a,'actual':b,'change_type':'CHANGED'})
 walk(expected,actual); return out
