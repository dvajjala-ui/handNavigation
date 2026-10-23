// A consent-driven recorder for the owned practice root, never the whole page.
window.HandNavigateTeachingRecorder=class {
  constructor(root,onChange=()=>{}) {
    this.root=root;this.onChange=onChange;this.active=false;this.events=[];
    this.listeners=[];
  }
  start(){
    this.stop();this.events=[];this.active=true;
    const sensitive=el=>Boolean(el.closest('[data-private]'))||el.type==='password'||
      /password|one-time-code|cc-|credit/i.test(el.autocomplete||'');
    const fieldEvent=el=>{
      if(!(el instanceof HTMLInputElement||el instanceof HTMLSelectElement||el instanceof HTMLTextAreaElement))return;
      if(sensitive(el)){this.push({op:'blocked',reason:'private_control'});return;}
      const field=el.dataset.hnField;
      if(!['topic','layout','captions'].includes(field)){this.push({op:'blocked',reason:'unknown_control'});return;}
      const op=field==='topic'?'fill':field==='layout'?'select':'check';
      const value=field==='captions'?el.checked:el.value;
      this.push({op,field,value});
    };
    const input=e=>{if(e.target instanceof HTMLInputElement && e.target.type!=='checkbox' || e.target instanceof HTMLTextAreaElement)fieldEvent(e.target);};
    const change=e=>{if(e.target instanceof HTMLSelectElement||e.target instanceof HTMLInputElement&&e.target.type==='checkbox')fieldEvent(e.target);};
    const click=e=>{
      const el=e.target.closest('button,a,[role="button"]');if(!el||!this.root.contains(el))return;
      if(sensitive(el)){this.push({op:'blocked',reason:'private_control'});return;}
      if(el.dataset.hnControl==='prepare')this.push({op:'click',control:'prepare'});
      else this.push({op:'blocked',reason:'unsupported_click'});
    };
    for(const [type,fn] of [['input',input],['change',change],['click',click]]){
      this.root.addEventListener(type,fn,true);this.listeners.push([type,fn]);
    }
    this.onChange(this.snapshot());
  }
  push(event){
    if(!this.active)return;
    if(this.events.length>=48){this.events=[{op:'blocked',reason:'event_budget_exceeded'}];this.stop();return;}
    const last=this.events[this.events.length-1];
    // Only adjacent edits to the same field are collapsed; clicks are boundaries.
    if(event.field&&last&&last.field===event.field&&last.op===event.op)this.events.pop();
    this.events.push(event);this.onChange(this.snapshot());
  }
  captureInputs(){
    if(!this.active)throw new Error('Start recording first');
    for(const field of ['topic','layout','captions']){
      const el=this.root.querySelector('[data-hn-field="'+field+'"]');
      if(el.closest('[data-private]')||el.type==='password'||/password|one-time-code|cc-|credit/i.test(el.autocomplete||'')) {this.push({op:'blocked',reason:'private_control'});continue;}
      this.push({op:field==='topic'?'fill':field==='layout'?'select':'check',field,value:field==='captions'?el.checked:el.value});
    }
  }
  stop(){for(const [type,fn] of this.listeners)this.root.removeEventListener(type,fn,true);this.listeners=[];this.active=false;this.onChange(this.snapshot());return this.snapshot();}
  snapshot(){return {schema_version:2,adapter_id:'owned-form-v1',capture_state:this.active?'RECORDING':'STOPPED',events:JSON.parse(JSON.stringify(this.events)),
    provenance:'Captured browser events; capture alone does not prove a human performed them'};}
};

void 0;
