'use strict';
const fs=require('node:fs'),path=require('node:path');
const {hash,clone,taskHash,validate,atomicWrite,PRIVATE}=require('../desktop/core.cjs');
const {BUILTINS,sources}=require('./sources.cjs');
function compile(task,runs){
  validate(task);
  if(task.type!=='images'||task.archived||task.approvedSha!==taskHash(task)||task.sha!==task.approvedSha)throw new Error('Choose an approved image workflow.');
  if(!runs.some(r=>r.taskId===task.id&&r.sha===task.sha&&r.status==='VERIFIED'&&r.items?.length===task.count))throw new Error('Run and verify this version of the workflow before adding it as a source.');
  const dynamic=JSON.stringify([task.startUrl,task.steps,task.checks]);
  if(!dynamic.includes('{{topic}}')||[...dynamic.matchAll(/\{\{([^}]+)\}\}/g)].some(m=>m[1]!=='topic'))throw new Error('Collection sources must use {{topic}} as their only changing value.');
  if(task.steps.some(s=>s.blocked||PRIVATE.test(JSON.stringify(s.locator||{}))))throw new Error('Remove private controls before adding a collection source.');
  const source={id:'custom-'+hash(task.id).slice(0,16),name:task.name,searchUrl:task.startUrl,selector:task.sourceSelector,
    allowedOrigins:clone(task.allowedOrigins),imageOrigins:clone(task.imageOrigins),pagination:clone(task.pagination||{kind:'scroll',maxPages:30}),
    steps:clone(task.steps),checks:clone(task.checks),workflowId:task.id,workflowSha:task.sha};
  source.revision=hash(source);sources([source]);return source;
}
function read(folder){
  const file=path.join(folder,'source-recipes.json');if(!fs.existsSync(file))return [];
  const envelope=JSON.parse(fs.readFileSync(file,'utf8'));
  if(envelope.sha!==hash(envelope.data)||envelope.data?.schema!==1||!Array.isArray(envelope.data.recipes))throw new Error('Saved source recipes failed their integrity check. Preserve the file before restoring a backup.');
  const recipes=envelope.data.recipes;
  if(recipes.some(s=>!s.id.startsWith('custom-')))throw new Error('Saved sources cannot replace built-in providers.');
  if(recipes.length)sources(recipes);return recipes;
}
function load(folder,configured){
  const base=configured|| (process.env.HANDNAVIGATE_SOURCES_FILE?JSON.parse(fs.readFileSync(process.env.HANDNAVIGATE_SOURCES_FILE,'utf8')):BUILTINS);
  return clone(sources([...base,...read(folder)]));
}
function save(folder,recipe){
  const recipes=read(folder).filter(s=>s.id!==recipe.id);recipes.push(recipe);
  sources([...load(folder).filter(s=>s.id!==recipe.id),recipe]);write(folder,recipes);return recipe;
}
function remove(folder,id){const recipes=read(folder);if(!recipes.some(s=>s.id===id))throw new Error('Choose a saved custom source.');write(folder,recipes.filter(s=>s.id!==id));}
function write(folder,recipes){const data={schema:1,recipes};atomicWrite(path.join(folder,'source-recipes.json'),{sha:hash(data),data});}
module.exports={compile,read,load,save,remove};
