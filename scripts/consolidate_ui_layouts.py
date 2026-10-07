"""One-time migration of legacy component geometry; UI appearance lives in DesignSystem.css.
Run with tinycss2 installed. Never include legacy theme/important rules in the app.
"""
from pathlib import Path
import re
import subprocess
import tinycss2 as css
root=Path(__file__).resolve().parents[1]/'app/frontend/src'
files=['styles.css','Lifecycle.css','Momentum.css','SalesHub.css','IcpProfile.css','RescorePanel.css','ProductRedesign.css','AppPolish.css','BrandRefresh.css','PremiumMotion.css']
visual=re.compile(r'^(?:color|background(?:-.+)?|font(?:-.+)?|line-height|letter-spacing|text-shadow|box-shadow|border(?:-.+)?|outline(?:-.+)?|filter|backdrop-filter|-webkit-backdrop-filter|animation(?:-.+)?|transition(?:-.+)?|all|fill|stroke|accent-color|caret-color)$')
structural={'--kx-mobile-nav-height','--kx-mobile-nav-gap','--kx-page-bottom-space','--kx-sticky-actions-height','--kx-page','--kx-control'}
def migrate(nodes):
 out=[]
 for node in nodes:
  if node.type=='qualified-rule':
   selector=css.serialize(node.prelude).strip()
   # Global typography/shell and old decoration are owned by the new system.
   selectors=[s.strip() for s in selector.split(',')]
   if not re.search(r'\.[a-zA-Z_-]',selector) or any(x in selector for x in ['.shell>aside','.shell > aside','.shell main','.shell>main','.shell > main','.bottom-nav','.neo-header-brand','.mobile-menu-btn','.brand','.safe','::before','::after']):continue
   classes=set(re.findall(r'\.([a-zA-Z_-][a-zA-Z0-9_-]*)',selector))
   if classes <= {'shell','kp-motion-layer','kp-profile-layer'}:continue
   decls=[]
   for d in css.parse_declaration_list(node.content,skip_comments=True,skip_whitespace=True):
    if d.type!='declaration':continue
    if d.name.startswith('--') and d.name not in structural:continue
    if visual.match(d.name) or d.name in ['border-radius','opacity','transform','content','text-transform']:continue
    decls.append(d.name+':'+css.serialize(d.value).strip()+';')
   if decls:out.append(selector+'{'+''.join(decls)+'}')
  elif node.type=='at-rule' and node.content and node.lower_at_keyword in ['media','supports','container']:
   nested=migrate(css.parse_rule_list(node.content,skip_comments=True,skip_whitespace=True))
   if nested:out.append('@'+node.at_keyword+' '+css.serialize(node.prelude).strip()+'{\n'+nested+'\n}')
 return '\n'.join(out)
def original(f):
 return subprocess.check_output(['git','show','5d49277d39498fbaa9781752ecd344711bb63dd0:app/frontend/src/'+f],cwd=root,text=True)
text='\n'.join(migrate(css.parse_stylesheet(original(f),skip_comments=True,skip_whitespace=True)) for f in files)
(root/'LegacyLayouts.css').write_text('/* Migrated feature geometry only. No theme, shell, motion, or !important rules. */\n@layer legacy-layout {\n'+text+'\n}\n')
print('Layout bytes:',len(text))
