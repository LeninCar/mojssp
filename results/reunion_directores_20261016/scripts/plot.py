"""Scientific figures from processed CSV only. Uses existing matplotlib runtime.
No source/result modification, optimization, installation, or network activity.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parents[1]; T=OUT/'tables'; F=OUT/'figures'
plt.rcParams.update({'font.size':10,'axes.titlesize':12,'axes.labelsize':10,'figure.dpi':120,'savefig.dpi':180,'axes.spines.top':False,'axes.spines.right':False})
LABEL={'moead':'MOEA/D','nsga2':'NSGA-II','spea2':'SPEA2','uniform':'Uniforme','adaptive':'SW-UCB','scaled':'UCB escalado','guidance':'Padre externo (replay)','combined':'Combinado'}
COL={'moead':'#1565a7','nsga2':'#e08b13','spea2':'#8a50a0','uniform':'#777777','adaptive':'#b83939','scaled':'#168073','guidance':'#a66a2c','combined':'#dc64a8'}
ARMS=['MOEA/D','NSGA-II','SPEA2']; AC=['#1565a7','#e08b13','#8a50a0']
cat=[]
def read(n):return pd.read_csv(T/(n+'.csv'))
def finish(fig,n,title,design,source,explanation):
 fig.suptitle(title,fontweight='bold',y=.99)
 sourcepath=source+'.csv' if source=='05_inventario_instancias' else 'tables/'+source+'.csv'
 fig.text(.01,.012,design+'\nFuente: '+sourcepath,ha='left',va='bottom',fontsize=8)
 fig.tight_layout(rect=(0,.09,.87 if n=='19_frente_3d' else 1,.95));fig.savefig(F/(n+'.png'),bbox_inches='tight');fig.savefig(F/(n+'.svg'),bbox_inches='tight');plt.close(fig)
 cat.append(dict(id=n,title=title,design=design,source=sourcepath,explanation=explanation,png='figures/'+n+'.png',svg='figures/'+n+'.svg'))
def heat(ax,data,title,xlab='',ylab='',fmt='.3f',cmap='viridis'):
 im=ax.imshow(data.to_numpy(float),aspect='auto',cmap=cmap);ax.set_xticks(range(len(data.columns)),data.columns,rotation=35,ha='right');ax.set_yticks(range(len(data)),data.index);ax.set_title(title);ax.set_xlabel(xlab);ax.set_ylabel(ylab)
 if data.size<=90:
  for i in range(len(data)):
   for j in range(len(data.columns)):ax.text(j,i,format(data.iloc[i,j],fmt) if pd.notna(data.iloc[i,j]) else 'NA',ha='center',va='center',fontsize=8,color='black',bbox=dict(facecolor='white',alpha=.65,edgecolor='none',pad=1))
 return im

b=read('recent_base_means');runs=read('recent_runs');blocks=read('recent_blocks');a=read('recent_allocations');p=read('recent_paired_by_base');stats=read('recent_paired_statistics')
c=b[b.split=='confirmation'];methods=['moead','nsga2','spea2','uniform','adaptive','scaled','guidance']
fig,ax=plt.subplots(figsize=(12,6));h=c.pivot(index='instance',columns='method',values='hv')[methods].rename(columns=LABEL);im=heat(ax,h,'HV medio de tres semillas por instancia','Método','Instancia');fig.colorbar(im,ax=ax,label='HV normalizado (u.³)')
finish(fig,'01_hv_confirmacion','Comparación principal de calidad final','Confirmación interna; 3000 FE; 8 bases × 3 semillas por método','recent_base_means','Las filas muestran heterogeneidad entre bases. El HV absoluto no mide dificultad universal.')

fig,axs=plt.subplots(1,2,figsize=(12,5),sharey=True)
for ax,met in zip(axs,['hv','auc_hv']):
 for i,m in enumerate(['scaled','guidance']):
  d=p[(p.split=='confirmation')&(p.metric==met)&(p.treatment==m)&(p.control=='adaptive')].sort_values('instance');ax.scatter(d.delta,np.arange(len(d))+.12*i,label=LABEL[m],color=COL[m],s=50)
 ax.axvline(0,color='black',lw=1);ax.set_yticks(range(len(d)),d.instance);ax.set_xlabel('Diferencia pareada '+('HV' if met=='hv' else 'AUC-HV'));ax.legend();ax.grid(axis='x',alpha=.25)
finish(fig,'02_diferencias_pareadas','Ganancia respecto a SW-UCB original','Confirmación interna; 3000 FE; 8 medias de base, 3 semillas pareadas/base','recent_paired_by_base','Escalado mejora HV y AUC en las ocho bases; padre externo pierde HV en una.')

fig,ax=plt.subplots(figsize=(10,5))
bb=blocks[blocks.split=='confirmation']
for m in methods:
 d=bb[bb.method==m].groupby(['instance','fe']).hv_after.mean().reset_index().groupby('fe').hv_after.agg(['mean','std','count']);x=np.r_[0,d.index];y=np.r_[0,d['mean']];ax.plot(x,y,label=LABEL[m],color=COL[m]);
ax.set_xlabel('Evaluaciones acumuladas (FE)');ax.set_ylabel('HV medio (u.³)');ax.legend(ncol=2);ax.grid(alpha=.2)
finish(fig,'03_hv_fe','Calidad durante la búsqueda','Confirmación interna; 0–3000 FE; 8 bases × 3 semillas/método; medias, sin inferencia por punto','recent_blocks','Las trayectorias proceden de registros cada 50 FE; el origen (0,0) forma parte de AUC.')

fig,ax=plt.subplots(figsize=(9,5))
for m in methods:
 d=c[c.method==m];ax.scatter(d.seconds.mean(),d.hv.mean(),color=COL[m],s=90);ax.annotate(LABEL[m],(d.seconds.mean(),d.hv.mean()),xytext=(5,6),textcoords='offset points',fontsize=9)
ax.set_xlabel('Tiempo medio de búsqueda por ejecución (s)');ax.set_ylabel('HV final medio (u.³)');ax.grid(alpha=.2)
finish(fig,'04_calidad_tiempo','Calidad y coste computacional','Confirmación interna; 3000 FE; 8 bases × 3 semillas; replay excluye coste del control externo','recent_base_means','El tiempo incluye algoritmos y gestión online; no permite aislar el coste del selector.')

fig,axs=plt.subplots(1,2,figsize=(13,5))
for ax,m in zip(axs,['adaptive','scaled']):
 d=a[(a.split=='confirmation')&(a.method==m)].groupby(['instance','arm']).FE_share.mean().unstack()[ARMS];bottom=np.zeros(len(d))
 for arm,color in zip(ARMS,AC):ax.bar(np.arange(len(d)),100*d[arm],bottom=bottom,label=arm,color=color);bottom+=100*d[arm].to_numpy()
 ax.set_xticks(range(len(d)),[i.replace('confirmation_','') for i in d.index],rotation=45);ax.set_ylim(0,100);ax.set_ylabel('Presupuesto asignado (%)');ax.set_xlabel('Instancia');ax.set_title(LABEL[m]);ax.legend(fontsize=8)
finish(fig,'05_asignacion','Cómo cambia el reparto de FE','Confirmación interna; 3000 FE; 8 bases × 3 semillas; inicialización incluida','recent_allocations','Mayor desigualdad por sí sola no demuestra adaptación efectiva. Comparar con figura 02.')

co=read('recent_complementarity');fig,ax=plt.subplots(figsize=(11,5));d=co[(co.split=='confirmation')&(co.method=='scaled')].groupby(['instance','arm']).marginal_hv.mean().unstack()[ARMS]
x=np.arange(len(d))
for i,(arm,color) in enumerate(zip(ARMS,AC)):ax.bar(x+(i-1)*.24,d[arm],width=.24,label=arm,color=color)
ax.set_xticks(x,[i.replace('confirmation_','') for i in d.index],rotation=35);ax.set_xlabel('Instancia');ax.set_ylabel('HV exclusivo leave-one-arm-out (u.³)');ax.legend()
finish(fig,'06_contribuciones','Contribución marginal bajo asignación adaptativa','Confirmación interna; UCB escalado; 3000 FE totales; 8 bases × 3 semillas','recent_complementarity','No sumar estas contribuciones como HV total. Son archivos locales observados, no un experimento de eliminar brazos.')

hp=read('historical_front_projections');example='base_c02_10x10_b03_tard_high';d=hp[(hp.instance==example)&(hp.seed==42)&(hp.FE_per_arm==3000)];fig,axs=plt.subplots(1,3,figsize=(14,4.8))
for ax,xx,yy,xl,yl in zip(axs,['cmax','cmax','tardiness'],['tardiness','energy','energy'],['Cmax (u. tiempo)','Cmax (u. tiempo)','Tardanza total (u. tiempo)'],['Tardanza total (u. tiempo)','Energía (u. energía)','Energía (u. energía)']):
 for arm,color in zip(ARMS,AC):
  g=d[d.arm==arm];ax.scatter(g[xx],g[yy],s=14,label=arm,color=color,alpha=.6);g=g[g.in_union_nd];ax.scatter(g[xx],g[yy],s=30,facecolors='none',edgecolors=color)
 ax.set_xlabel(xl);ax.set_ylabel(yl);ax.legend(fontsize=8)
finish(fig,'07_frentes_proyecciones','Regiones exploradas por algoritmos individuales','Fase 2 histórica; '+example+'; semilla 42; 3000 FE/brazo, unión = 9000 FE','historical_front_projections','Círculos huecos: soluciones que sobreviven en la unión. Ejemplo ilustrativo, no generalización.')

inv=pd.read_csv(OUT/'05_inventario_instancias.csv');valid=inv[(inv.feature_status=='parsed')&(~inv.split.isin(['validation']))&(~inv.origin.str.contains('invalid',case=False,regex=True))];fig,axs=plt.subplots(1,3,figsize=(13,4.6))
for ax,col,label in zip(axs,['operations','machine_load_cv','relative_slack_mean'],['Operaciones (N; escala log)','CV de carga media por máquina','Holgura relativa media (sin contención)']):
 bins=np.geomspace(valid[col].min(),valid[col].max(),19) if col=='operations' else 18;ax.hist(valid[col].dropna(),bins=bins,color='#1565a7',edgecolor='white');ax.set_xlabel(label);ax.set_ylabel('Instancias únicas (hash)')
 if col=='operations':ax.set_xscale('log')
finish(fig,'08_caracterizacion','Distribución de las instancias disponibles','Datos no reservados; '+str(len(valid))+' archivos de contenido distinto; sin FE ni semillas de búsqueda','05_inventario_instancias','Los perfiles derivados están correlacionados; este histograma describe el inventario, no una muestra independiente.')

stand=read('standalone_per_instance');fig,ax=plt.subplots(figsize=(10,5));d=stand[stand.campaign=='loop_confirmation']
for arm,color in zip(ARMS,AC):
 g=d[d.method==arm].sort_values('operations');ax.scatter(g.operations,g.mean_hv,label=arm,color=color,s=55);ax.errorbar(g.operations,g.mean_hv,yerr=g.seed_sd,fmt='none',ecolor=color,alpha=.45,capsize=2)
ax.set_xscale('log');ax.set_xlabel('Operaciones (escala log)');ax.set_ylabel('HV medio ± DE entre 3 semillas (u.³)');ax.legend();ax.grid(alpha=.2)
finish(fig,'09_hv_tamano','Rendimiento individual frente al tamaño','Confirmación interna; 3000 FE; 8 bases × 3 semillas; tamaño y perfil confundidos','standalone_per_instance','Hay dos geometrías con 200 operaciones. No se ajusta una regla de especialización a ocho observaciones.')

fig,axs=plt.subplots(1,2,figsize=(12,5))
for ax,met in zip(axs,['genetic_diversity','hv']):
 vals=[];labs=[];colors=[]
 for split,m,control in [('confirmation','scaled','adaptive'),('confirmation','guidance','adaptive'),('development','combined','scaled')]:
  dd=p[(p.split==split)&(p.treatment==m)&(p.control==control)&(p.metric==met)];vals.append(dd.delta);labs.append(LABEL[m]+'\n'+('confirmación' if split=='confirmation' else 'desarrollo')+'\nvs '+LABEL[control]);colors.append(COL[m])
 ax.boxplot(vals,tick_labels=labs,showmeans=True);ax.axhline(0,color='black',lw=1);ax.set_ylabel('Δ '+met);ax.tick_params(axis='x',labelsize=8)
finish(fig,'10_cooperacion_diversidad','Diversidad y calidad responden de forma distinta','3000 FE; confirmación n=8 bases × 3 semillas; combinado sólo desarrollo n=6 × 3','recent_paired_by_base','La diversidad genotípica es una distancia en poblaciones registradas durante la campaña, no cobertura del Pareto óptimo.')

u=read('ucb_terms');fig,axs=plt.subplots(1,2,figsize=(12,4.8))
for ax,m in zip(axs,['adaptive','scaled']):
 d=u[(u.split=='confirmation')&(u.method==m)&(~u.probe)&(u.selected)]
 for col,label in [('exploitation','Explotación'),('exploration','Exploración')]:
  g=d.groupby('fe_before')[col].median();ax.plot(g.index,g,label=label)
 ax.set_xlabel('FE antes de elegir brazo');ax.set_ylabel('Mediana del término UCB (u. recompensa)');ax.set_title(LABEL[m]);ax.legend();ax.grid(alpha=.2)
finish(fig,'11_escala_ucb','Escala de explotación y exploración','Confirmación interna; 3000 FE; 8 bases × 3 semillas; brazo elegido con estadística finita; probes excluidos','ucb_terms','Los términos se reconstruyen antes de decidir y se muestran para el brazo elegido; escalas de ejes independientes. Los brazos ausentes de ventana tienen UCB infinito y no entran en estas medianas.')

hist=read('historical_runs_separated');ph=hist[hist.campaign=='page_hinkley_final'];fig,axs=plt.subplots(1,2,figsize=(11,4.8));means=ph.groupby(['instance','method']).hv.mean().unstack()
for i,m in enumerate(['ucb1','dmab_ph','sw_ucb']):axs[0].scatter(np.full(len(means),i),means[m],s=30);axs[0].plot(i,means[m].mean(),'k_',ms=24,mew=3)
axs[0].set_xticks(range(3),['UCB1','UCB1 + PH','SW-UCB']);axs[0].set_ylabel('HV a 5000 FE (u.³)');delta=means.dmab_ph-means.sw_ucb;axs[1].barh(delta.index,delta,color=np.where(delta>=0,'#168073','#b83939'));axs[1].axvline(0,color='black');axs[1].set_xlabel('ΔHV PH − SW-UCB')
finish(fig,'12_page_hinkley','Page-Hinkley no acredita una ventaja','Histórico PH; 5000 FE; 10 bases de desarrollo × semillas 42,123,456; 90 ejecuciones','historical_runs_separated','Contraste histórico Holm PH vs SW-UCB p=0.320312. La calibración y comparación usan las mismas bases.')

fig,ax=plt.subplots(figsize=(10,5));hs=read('historical_summary');d=hs[hs.campaign=='phase2_budget']
for m,g in d.groupby('method'):
 g=g.sort_values('budget');colors={'MOEA/D':AC[0],'NSGA-II':AC[1],'SPEA2':AC[2],'Adaptive Portfolio (DMAB)':COL['adaptive'],'Uniform Portfolio (Round-Robin)':COL['uniform']};ax.plot(g.budget,g.mean_hv,'o-',label=m,color=colors[m])
ax.set_xlabel('Evaluaciones acumuladas (FE)');ax.set_ylabel('HV medio por base (u.³)');ax.legend(fontsize=8);ax.grid(alpha=.2)
finish(fig,'13_presupuestos_historicos','El efecto del presupuesto se estudia dentro de cada trayectoria','Fase 2; 10 bases × 3 semillas × 5 métodos; cortes 1000/3000/5000 de 150 ejecuciones','historical_summary','No tratar 450 cortes como ejecuciones independientes. El piloto de 1000 FE tampoco es una réplica nueva de calidad.')

corr=read('exploratory_feature_correlations');fig,axs=plt.subplots(1,2,figsize=(14,6))
feature_labels={'energy_mode_contrast_mean':'Contraste energético','jobs_machines_ratio':'Trabajos / máquinas','machine_load_cv':'CV carga por máquina','modes_max':'Número de modos','operations':'Operaciones','processing_cv':'CV procesamiento','relative_slack_mean':'Holgura relativa','release_mean':'Release medio','time_energy_within_operation_correlation':'Correlación tiempo–energía'}
for ax,camp,fe in [(axs[0],'phase1_40_profiles',1000),(axs[1],'loop_confirmation',3000)]:
 d=corr[(corr.campaign==camp)&(corr.budget==fe)].pivot(index='feature',columns='contrast',values='spearman_rho').rename(index=feature_labels);im=heat(ax,d,('Fase 1: nominales' if camp.startswith('phase1') else 'Confirmación')+'; '+str(fe)+' FE',fmt='.2f',cmap='coolwarm');im.set_clim(-1,1);fig.colorbar(im,ax=ax,label='ρ de Spearman')
finish(fig,'14_correlaciones','Asociaciones exploratorias, sin evidencia causal','Fase 1: 8 bases nominales × 5 semillas; confirmación: 8 bases × 3 semillas; modos constantes → NA','exploratory_feature_correlations','Las diferencias entre campañas y perfiles impiden usar estas correlaciones como un selector entrenado.')

fig,axs=plt.subplots(1,2,figsize=(13,6),sharey=True)
for ax,m in zip(axs,['adaptive','scaled']):
 d=bb[bb.method==m].copy();d['row']=d.instance+' s'+d.seed.astype(str);d['code']=d.arm_name.map(dict(zip(ARMS,range(3))));piv=d.pivot(index='row',columns='block_index',values='code');im=ax.imshow(piv,aspect='auto',vmin=-.5,vmax=2.5,cmap=matplotlib.colors.ListedColormap(AC));ax.set_yticks(range(len(piv)),[x.replace('confirmation_','') for x in piv.index],fontsize=7);ax.set_xlabel('Bloque de 50 FE (índice desde 0)');ax.set_title(LABEL[m]);cb=fig.colorbar(im,ax=ax,ticks=range(3),fraction=.025,pad=.02);cb.ax.set_yticklabels(ARMS,fontsize=8)
finish(fig,'15_trayectorias_asignacion','Asignación observada bloque a bloque','Confirmación interna; 3000 FE = 60 bloques; 8 bases × 3 semillas por política','recent_blocks','Las revisitas se mantienen incluso con UCB escalado. La figura muestra decisiones, no ganancias causales por brazo.')

ov=read('archive_overlap');fig,axs=plt.subplots(1,2,figsize=(10,4.6))
for ax,col,label in zip(axs,['genotype_jaccard','objective_jaccard'],['Genotipos','Vectores objetivo']):
 d=ov[(ov.split=='confirmation')&(ov.method=='scaled')].groupby(['arm1','arm2'])[col].mean().unstack().reindex(index=ARMS,columns=ARMS);im=heat(ax,d,label,fmt='.3f');fig.colorbar(im,ax=ax,label='Jaccard medio [0,1]')
finish(fig,'16_solapamiento','Coincidencia entre archivos locales','Confirmación interna; UCB escalado; 3000 FE; 8 bases × 3 semillas','archive_overlap','Jaccard exacto bajo no implica cobertura volumétrica distinta: puntos diferentes pueden dominar regiones parecidas.')

st=read('stagnation');fig,axs=plt.subplots(1,2,figsize=(11,4.8));dd=st[st.split=='confirmation'];mm=['uniform','adaptive','scaled','guidance']
for ax,col,yl in zip(axs,['FE_after_two_own_zero_gains','positive_recoveries'],['FE después de dos recompensas propias nulas','Recuperaciones positivas por ejecución']):
 ax.boxplot([dd[dd.method==m][col] for m in mm],tick_labels=[LABEL[m] for m in mm],showmeans=True);ax.set_ylabel(yl);ax.tick_params(axis='x',rotation=20,labelsize=8)
finish(fig,'17_estancamiento','Evitar ceros y conservar oportunidades de recuperación','Confirmación interna; 3000 FE; 8 bases × 3 semillas/método; cero ≤ 1e−14','stagnation','Una recompensa nula se refiere al archivo global presente; no prueba incapacidad del algoritmo.')

sp=read('feature_performance_scatter');fig,axs=plt.subplots(1,3,figsize=(14,4.6));d=sp[sp.campaign=='loop_confirmation']
for ax,f,xl in zip(axs,['machine_load_cv','relative_slack_mean','processing_cv'],['CV carga por máquina','Holgura relativa media','CV procesamiento medio por operación']):
 for con,g in d.groupby('contrast'):ax.scatter(g[f],g.hv_delta,label=con,s=45,color=AC[1] if con.startswith('NSGA') else AC[2])
 ax.axhline(0,color='black',lw=1);ax.set_xlabel(xl);ax.set_ylabel('ΔHV frente a MOEA/D');ax.legend(fontsize=7)
finish(fig,'18_caracteristicas_rendimiento','Características estructurales y brechas individuales','Confirmación interna; 3000 FE; 8 bases × 3 semillas; asociaciones exploratorias','feature_performance_scatter','Tamaño, perfil y configuración del generador no están cruzados factorialmente en esta campaña.')

fig=plt.figure(figsize=(9,6));ax=fig.add_subplot(111,projection='3d')
for arm,color in zip(ARMS,AC):
 g=hp[(hp.instance==example)&(hp.seed==42)&(hp.FE_per_arm==3000)&(hp.arm==arm)];ax.scatter(g.cmax,g.tardiness,g.energy,s=15,color=color,label=arm,alpha=.7)
ax.set_xlabel('Cmax (u. tiempo)');ax.set_ylabel('T (u. tiempo)');ax.set_zlabel('');fig.text(.91,.52,'E (u. energía)',rotation=90,va='center',fontsize=10);ax.legend()
finish(fig,'19_frente_3d','Frentes observados en los tres objetivos','Fase 2 histórica; '+example+'; semilla 42; 3000 FE/brazo, 9000 FE de unión','historical_front_projections','No se conoce el frente Pareto óptimo. Esta visualización compara aproximaciones evaluadas.')

un=read('historical_standalone_union');fig,axs=plt.subplots(1,2,figsize=(11,4.8))
for arm,color in zip(ARMS,AC):
 g=un[un.arm==arm].groupby('FE_per_arm').marginal_hv.mean();axs[0].plot(g.index,g,'o-',color=color,label=arm)
g=un.drop_duplicates(['instance','seed','FE_per_arm']).groupby('FE_per_arm').union_gain.mean();axs[1].plot(g.index,g,'o-',color='#168073');axs[0].set_xlabel('FE por brazo (unión cuesta 3×)');axs[1].set_xlabel('FE por brazo (unión cuesta 3×)');axs[0].set_ylabel('Contribución exclusiva media (HV u.³)');axs[1].set_ylabel('HV(unión) − mejor HV individual (u.³)');axs[0].legend()
finish(fig,'20_complementariedad_fe','Complementariedad pasiva y su coste','Fase 2; 10 bases × 3 semillas; cortes por brazo 1000/3000/5000; unión 3000/9000/15000 FE','historical_standalone_union','Ganancia de unión positiva no demuestra que un portafolio gane al mejor individual a igual FE total.')

fig,ax=plt.subplots(figsize=(10,5));features=['machine_load_cv','processing_cv','relative_slack_mean','energy_mode_contrast_mean','release_mean','jobs_machines_ratio'];dd=inv[inv.instance.str.startswith('confirmation_')].set_index('instance')[features].astype(float);z=((dd-dd.mean())/dd.std(ddof=0)).rename(columns=feature_labels);im=heat(ax,z,'Características estandarizadas dentro de confirmación',fmt='.1f',cmap='coolwarm');fig.colorbar(im,ax=ax,label='Desviaciones estándar respecto a 8 bases')
finish(fig,'21_perfiles_instancias','Las instancias difieren en más características que el tamaño','Confirmación interna; 8 bases, sin búsqueda adicional; FE no aplica','05_inventario_instancias','La estandarización sirve para comparar columnas con unidades distintas; no es un índice de dificultad.')

fig,axs=plt.subplots(1,2,figsize=(11,4.8));modes=read('mode_values');dd=modes[modes.instance=='confirmation_01_10x10'];g=dd.groupby('mode')[['duration','energy']].mean();axs[0].plot(g.index,g.duration,'o-');axs[1].plot(g.duration,g.energy,'o-')
for i,r in g.iterrows():axs[1].annotate('modo '+str(i),(r.duration,r.energy),xytext=(3,3),textcoords='offset points',fontsize=8)
axs[0].set_xlabel('Identificador del modo');axs[0].set_ylabel('Duración media (u. tiempo)');axs[1].set_xlabel('Duración media (u. tiempo)');axs[1].set_ylabel('Energía media (u. energía)')
finish(fig,'22_modos_energia','Intercambio entre tiempo y energía por modo','Instancia confirmation_01_10x10; 100 operaciones, 5 modos; sin FE ni semillas de búsqueda','mode_values','El ejemplo describe modos existentes. El número de modos no varía entre las bases comparadas.')

fig,ax=plt.subplots(figsize=(10,5));timegrid=np.linspace(0,50,101)
for m in methods:
 trajectories=[]
 for (ins,s),g in bb[bb.method==m].groupby(['instance','seed']):
  g=g.sort_values('elapsed');xx=np.r_[0,g.elapsed];yy=np.r_[0,g.hv_after];idx=np.searchsorted(xx,timegrid,side='right')-1;val=yy[np.clip(idx,0,len(yy)-1)].astype(float);trajectories.append(val)
 arr=np.array(trajectories);n=np.isfinite(arr).sum(axis=0);means=np.divide(np.nansum(arr,axis=0),n,out=np.full(len(n),np.nan),where=n>0);# Do not average survivors: require all 24 executions at risk.
 means[n<len(arr)]=np.nan;ax.plot(timegrid,means,label=LABEL[m],color=COL[m])
ax.set_xlabel('Tiempo de búsqueda (s)');ax.set_ylabel('HV medio (u.³)');ax.legend(ncol=2,fontsize=8);ax.grid(alpha=.2)
finish(fig,'23_hv_tiempo','Calidad frente al tiempo medido','Confirmación interna; 3000 FE máximo; 8 bases × 3 semillas/método; HV final constante tras terminar','recent_blocks','Se conserva el último HV al concluir cada corrida: no se extrapolan mejoras ni se promedian sólo las ejecuciones lentas.')

(F/'figure_manifest.json').write_text(json.dumps(cat,ensure_ascii=False,indent=2),encoding='utf-8')
print('Created',len(cat),'figures in PNG and SVG')
