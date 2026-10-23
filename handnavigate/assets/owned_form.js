// Owned fixture logic. Kept separate from recorder and output expectations.
window.HandNavigatePractice = {
  mount(root, scenario='normal') {
    const button=root.querySelector('[data-hn-control="prepare"]');
    const output=root.querySelector('[data-testid="preview-output"]');
    button.addEventListener('click',()=>{
      const values={topic:root.querySelector('[data-hn-field="topic"]').value,
        layout:root.querySelector('[data-hn-field="layout"]').value,
        captions:root.querySelector('[data-hn-field="captions"]').checked};
      if(!values.topic.trim())return;
      if(scenario==='missing-output')return;
      if(scenario==='dialog'){alert('Unexpected confirmation');return;}
      if(scenario==='wrong-topic')values.topic='WRONG TOPIC';
      const render=()=>{
        output.querySelector('[data-testid="result-topic"]').textContent=values.topic;
        output.querySelector('[data-testid="result-layout"]').textContent=values.layout;
        output.querySelector('[data-testid="result-captions"]').textContent=values.captions?'yes':'no';
        output.hidden=false;
      };
      if(scenario==='delayed-output')setTimeout(render,180);else render();
    });
    if(scenario==='ambiguous-control')button.after(button.cloneNode(true));
  }
};
