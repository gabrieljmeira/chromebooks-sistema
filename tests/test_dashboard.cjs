const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { pendingAlerts } = require('../static/alerts.js');
function setup() {
  const nodes = {};
  for (const id of ['dashboard-content','sync-status','alerts','sound-status']) nodes[id] = {
    textContent: '', children: [], addEventListener() {}, contains() { return false; },
    querySelectorAll() { return []; }, prepend(item) { this.children.unshift(item); },
    replaceChildren() { this.children = []; }, append() {},
  };
  const listeners = {}, saved = new Map();
  let timer, tones = 0;
  let data = {html:'', pending:[], loans:[], server_time:'2026-10-14T12:00:00-03:00'};
  class AudioContext {
    constructor() { this.state='suspended'; this.currentTime=0; }
    async resume() { this.state='running'; }
    createOscillator() { tones++; return {frequency:{},connect(){},start(){},stop(){},disconnect(){}}; }
    createGain() { return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}}; }
  }
  const context = {document:{getElementById:id=>nodes[id],addEventListener:(type,fn)=>listeners[type]=fn,
    createElement:()=>({}), activeElement:null},window:{AudioContext},navigator:{},
    localStorage:{getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)},
    fetch:async()=>({ok:true,status:200,json:async()=>data}),
    setTimeout:fn=>timer=fn,LoanAlerts:{pendingAlerts}};
  vm.runInNewContext(fs.readFileSync('static/dashboard.js','utf8'),context);
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  return {nodes,listeners,settle,get tones(){return tones;}, async refresh(next){data=next;await timer();},get data(){return data;}};
}
test('novo pedido aguarda interação, toca e não se repete; prazo e pré-alerta tocam',async()=>{
  const app=setup();await app.settle();
  await app.refresh({...app.data,pending:[{id:1}]});
  assert.equal(app.tones,0);
  assert.match(app.nodes.alerts.children[0].textContent,/Novo pedido #1/);
  await app.listeners.click();assert.equal(app.tones,6);
  await app.refresh(app.data);assert.equal(app.tones,6);
  await app.refresh({...app.data,pending:[{id:1},{id:2}]});assert.equal(app.tones,12);
  await app.refresh({...app.data,pending:[],loans:[{id:1,remaining:1,expected:'2026-10-14T12:05:00-03:00'}]});
  assert.equal(app.tones,18);
  await app.refresh(app.data);assert.equal(app.tones,18);
  await app.refresh({...app.data,server_time:'2026-10-14T12:05:00-03:00'});assert.equal(app.tones,24);
  await app.refresh(app.data);assert.equal(app.tones,24);
});
test('interação sem aviso não toca; teclado também libera som',async()=>{
  const app=setup();await app.settle();await app.listeners.keydown();assert.equal(app.tones,0);
  await app.refresh({...app.data,pending:[{id:3},{id:4}]});assert.equal(app.tones,6);
  assert.equal(app.nodes.alerts.children.length,2);
});
