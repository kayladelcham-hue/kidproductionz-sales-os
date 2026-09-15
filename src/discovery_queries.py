"""Known business evidence only; lazy query progression."""
def queries(row):
    def quoted(v):return '"'+' '.join(str(v or '').replace('"','').split())+'"'
    name=row.get('name') or row.get('company_name','')
    if not name:return []
    result=[' '.join(quoted(v) for v in (name,row.get('city'),row.get('state')) if v)]
    if not row.get('social'):result.append(quoted(name)+' '+quoted(row.get('city',''))+' Instagram')
    strong=row.get('phone') or row.get('address')
    if strong:result.append(quoted(name)+' '+quoted(strong))
    return list(dict.fromkeys(result))
