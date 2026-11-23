import fs from 'node:fs';
import vm from 'node:vm';
import {Context} from '@deepseek-ai/cordis';
import AgentRegistry from '@deepseek-ai/dsh-agent';
import AgentLoop from '@deepseek-ai/dsh-agent-loop';
import SessionStore from '@deepseek-ai/dsh-session';
import Projection from '@deepseek-ai/dsh-session-projection';
import SystemPrompt from '@deepseek-ai/dsh-system-prompt';
import Tools from '@deepseek-ai/dsh-tools';
import * as Native from '@deepseek-ai/dsh-tool-executor-native';
import LlmRuntime,{LlmAdapter,createUserMessage} from '@deepseek-ai/dsh-llm';

const [pluginFile,batchFile,outFile]=process.argv.slice(2);
const config=JSON.parse(fs.readFileSync(new URL('./settings.json',import.meta.url)));
const code=new vm.Script('(()=>{'+fs.readFileSync(pluginFile,'utf8')+'\n;return JSON.stringify(next(q,h,s));})()');
const batch=JSON.parse(fs.readFileSync(batchFile));
const user=text=>createUserMessage({source:{kind:'user'},content:[{type:'text',text}]});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const done=new Set(fs.existsSync(outFile)?fs.readFileSync(outFile,'utf8').trim().split('\n').filter(Boolean).map(l=>JSON.parse(l).key):[]);

async function query(prompt,seed){
  const request={model:config.model,messages:[{role:'system',content:config.system},{role:'user',content:prompt}],temperature:0,top_p:1,max_tokens:300,seed,provider:{order:['Groq'],allow_fallbacks:false}};
  let last;
  for(let i=0;i<7;i++){
    try{
      const resp=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+process.env.OPENROUTER_API_KEY,'Content-Type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(90000)});
      if(!resp.ok) throw Error('HTTP '+resp.status+' '+(await resp.text()).slice(0,180));
      const data=await resp.json(),choice=data.choices?.[0];
      if(typeof choice?.message?.content!=='string'||data.provider!=='Groq'||data.model!==config.model) throw Error('invalid response '+JSON.stringify(data.error||{}));
      return {request,text:choice.message.content,finish:choice.finish_reason,usage:data.usage,provider:data.provider,model:data.model};
    }catch(e){last=e;if(i<6) await sleep(300*2**i);}
  }
  throw last;
}
async function episode(task){
  const q=task.input, history=[],events=[];
  const sandbox=vm.createContext({},{codeGeneration:{strings:false,wasm:false}});
  vm.runInContext('const q='+JSON.stringify(q)+';let h=[];const s={};',sandbox);
  function decide(){
    vm.runInContext('h='+JSON.stringify(history.map(({text,finish})=>({text,finish}))),sandbox);
    const result=JSON.parse(code.runInContext(sandbox,{timeout:200}));
    if(result!==null && (typeof result!=='string'||!result.trim()||result.length>80000)) throw Error('Invalid plugin output');
    return result;
  }
  let pending=decide(),failure;
  class Adapter extends LlmAdapter{
    async resolveModel(provider,id){return {provider,id,name:id};}
    async *stream(options){
      try{
        const last=options.messages.at(-1);
        const prompt=last.content.map(b=>b.text).join('');
        if(last.role!=='user'||prompt!==pending) throw Error('DSH message projection mismatch');
        // A fresh PICTURE-style chat for each admitted step; only explicit plugin state carries over.
        const call=await query(prompt,task.seed);
        history.push(call);const text=call.text;
        yield {type:'block-start',index:0,blockType:'text'};yield {type:'text-delta',index:0,text};
        yield {type:'block-end',index:0,block:{type:'text',text}};
        yield {type:'usage',usage:{inputTokens:call.usage.prompt_tokens,outputTokens:call.usage.completion_tokens}};
        yield {type:'finish',reason:{kind:call.finish==='length'?'max-tokens':'stop'}};
      }catch(e){failure=e;throw e;}
    }
  }
  const ctx=new Context();
  try{
    for(const p of [LlmRuntime,SessionStore,Projection,SystemPrompt,Tools,Native,AgentRegistry])await ctx.plugin(p);
    await ctx.plugin(AgentLoop,{agents:[]});
    ctx.llm.registerAdapter(['openrouter'],new Adapter());
    ctx.on('agent/pre-step',async(payload,next)=>{
      const decision=await next();events.push('agent/pre-step');
      return {...decision,messages:[user(pending)],startsRequestSeries:true};
    });
    ctx.on('agent/turn-stopping',({agent})=>{
      events.push('agent/turn-stopping');
      if(failure||history.length>=3)return;
      try{pending=decide();if(pending!==null)agent.steer(user(pending));}
      catch(e){failure=e;throw e;}
    });
    const agent=await ctx.agentLoop.create('question-'+task.key,{provider:'openrouter',model:config.model,maxTokens:300});
    agent.followup(user('Begin'));await agent.whenIdle();
    if(failure)throw failure;
    if(!history.length||events.filter(x=>x==='agent/pre-step').length!==history.length)throw Error('Missing completed DSH step: '+JSON.stringify(events)+' '+JSON.stringify(agent.session.snapshotEvents().slice(-3)).slice(0,800));
    return {key:task.key,line:task.line,seed:task.seed,calls:history,events};
  }finally{await ctx.fiber.dispose();}
}
const jobs=batch.filter(t=>!done.has(t.key));let cursor=0,errors=0;
async function worker(){while(cursor<jobs.length){const t=jobs[cursor++];try{const row=await episode(t);fs.appendFileSync(outFile,JSON.stringify(row)+'\n');}catch(e){errors++;if(errors<=5)console.error(t.key,e.stack);if(errors>=12)cursor=jobs.length;}}}
await Promise.all(Array.from({length:Math.min(24,jobs.length)},worker));
if(errors)process.exitCode=1;
