import React,{useEffect,useRef,useState} from 'react';
import {api} from './api';
import ReactMarkdown from 'react-markdown';

type Message={
  role:'user'|'assistant';
  content:string;
};

export default function SalesAgent({campaign}:{campaign:string}){
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
      const result=await api.aiChat({
        message,
        campaign,
        conversation:history
      });

      setMessages(prev=>[
        ...prev,
        {role:'assistant',content:result.reply}
      ]);
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
        onClick={()=>setOpen(true)}
      >
        ✦ AI Agent
      </button>
    }

    {open&&
      <section className="ai-agent-panel">

        <header className="ai-agent-header">
          <div>
            <strong>✦ AI Sales Agent</strong>
            <small>Powered by your Sales OS</small>
          </div>

          <button onClick={()=>setOpen(false)}>×</button>
        </header>

        <div className="ai-agent-messages">

          {messages.length===0&&
            <div className="ai-agent-welcome">
              <div className="ai-agent-icon">✦</div>

              <h2>What are we working on?</h2>

              <p>
                Ask about your leads, priorities,
                follow-ups, pipeline, or outreach.
              </p>

              <button onClick={()=>send('Who should I call first today and why?')}>
                Who should I call first?
              </button>

              <button onClick={()=>send('What follow-ups need my attention?')}>
                Check my follow-ups
              </button>

              <button onClick={()=>send('Analyze my current sales pipeline.')}>
                Analyze my pipeline
              </button>
            </div>
          }

          {messages.map((m,i)=>
            <div
              key={i}
              className={`ai-message ${m.role}`}
            >
              <small>{m.role==='assistant'?'AI':'YOU'}</small>
              <div className="ai-message-content">{m.role==='assistant'?<ReactMarkdown>{m.content}</ReactMarkdown>:m.content}</div>
            </div>
          )}

          {loading&&
            <div className="ai-message assistant">
              <small>AI</small>
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
            placeholder="Ask your Sales OS..."
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

