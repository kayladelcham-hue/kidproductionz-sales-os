import React,{useEffect,useRef,useState} from 'react';
import {api} from './api';
import ReactMarkdown from 'react-markdown';

type Message={
  role:'user'|'assistant';
  content:string;
  businesses?:any[];
};

export default function SalesAgent({campaign,discoveryIds=[],onOpenBusiness,onDiscover}:{campaign:string;discoveryIds?:number[];onOpenBusiness?:(id:number)=>void;onDiscover?:()=>void}){
  const [open,setOpen]=useState(false);
  const [messages,setMessages]=useState<Message[]>([]);
  const [input,setInput]=useState('');
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const bottom=useRef<HTMLDivElement|null>(null);

  useEffect(()=>{
    bottom.current?.scrollIntoView({behavior:'smooth'});
  },[messages,loading]);

  const send=async(text?:string)=>{
    const message=(text??input).trim();
    if(!message||loading)return;

    const history=messages.slice(-10);
    const userMessage:Message={role:'user',content:message};

    setMessages(prev=>[...prev,userMessage]);
    setInput('');
    setError('');
    setLoading(true);

    try{
      const discoveryQuestion=/ideal customer|who.*sell|potential customer|business.*fit|information.*missing|compare.*(lead|business)|qualification|draft.*message/i.test(message);
      const result=discoveryQuestion?await api.discoveryExplain({question:message,campaign,business_ids:discoveryIds.slice(0,5)}):await api.aiChat({message,campaign,conversation:history});
      setMessages(prev=>[...prev,{role:'assistant',content:result.reply,businesses:result.businesses}]);
    }catch(e:any){
      setError(e?.message||'AI Agent unavailable');
    }finally{
      setLoading(false);
    }
  };

  return <>
    {!open&&
      <button
        className="ai-agent-launcher"
        aria-label="Open Skye sales assistant"
        onClick={()=>setOpen(true)}
      >
        ✦ Skye
      </button>
    }

    {open&&
      <section className="ai-agent-panel" role="dialog" aria-label="Skye">

        <header className="ai-agent-header">
          <div>
            <strong>✦ Skye</strong>
            <small>Your business helper</small>
          </div>

          <button aria-label="Close Skye" onClick={()=>setOpen(false)}>×</button>
        </header>

        <div className="ai-agent-messages">

          {messages.length===0&&
            <div className="ai-agent-welcome">
              <div className="ai-agent-icon">✦</div>

              <h2>What are we working on?</h2>

              <p>
                Ask why a business appeared, what to check, or how to take the next step.
              </p>

              <button onClick={()=>send('Find potential customers for what I sell.')}>
                Help me find potential customers
              </button>

              <button onClick={()=>send('Why does this business fit?')}>
                Why does this business fit?
              </button>

              <button onClick={()=>send('What information is missing?')}>
                What information is missing?
              </button>
              <button disabled={discoveryIds.length<2} onClick={()=>send('Compare these businesses.')}>Compare these businesses</button>
              <button onClick={onDiscover}>Find potential customers</button>
            </div>
          }

          {messages.map((m,i)=>
            <div
              key={i}
              className={`ai-message ${m.role}`}
            >
              <small>{m.role==='assistant'?'SKYE':'YOU'}</small>
              <div className="ai-message-content">{m.role==='assistant'?<ReactMarkdown>{m.content}</ReactMarkdown>:m.content}</div>{m.businesses?.map(b=><article key={b.id}><button onClick={()=>{setOpen(false);onOpenBusiness?.(b.id)}}>{b.name}</button><p>{b.fit}</p><p>Known: {b.known.join(' · ')||'No confirmed criterion match'}</p><p>Missing: {b.missing.join(' · ')}</p><p>My suggestion: {({QUALIFIED:'Looks like a fit',NEEDS_RESEARCH:'Not sure',DISQUALIFIED:'Not a fit'} as any)[b.suggested_decision]}. {b.explanation}</p>{b.sources.map((s:any)=><a key={s.url} href={s.url} target="_blank" rel="noreferrer">{s.label} ↗</a>)}</article>)}
            </div>
          )}

          {loading&&
            <div className="ai-message assistant">
              <small>SKYE</small>
              <div>Thinking...</div>
            </div>
          }

          {error&&
            <div className="ai-agent-error">{error}</div>
          }

          <div ref={bottom}/>
        </div>

        <footer className="ai-agent-input">
          <textarea
            value={input}
            onChange={e=>setInput(e.target.value)}
            onKeyDown={e=>{
              if(e.key==='Enter'&&!e.shiftKey){
                e.preventDefault();
                send();
              }
            }}
            aria-label="Ask Skye" placeholder="Ask Skye..."
            rows={1}
          />

          <button
            onClick={()=>send()}
            disabled={!input.trim()||loading}
          >
            ↑
          </button>
        </footer>

      </section>
    }
  </>;
}

