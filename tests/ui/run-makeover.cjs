// Requires jsdom in the runner's module path. This is a DOM test, not a browser.
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',{url:'http://unit.test'});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,IS_REACT_ACT_ENVIRONMENT:true,requestAnimationFrame:fn=>fn()});
dom.window.matchMedia=()=>({matches:true});
dom.window.HTMLElement.prototype.scrollIntoView=function(){};
import(process.argv[2]).then(()=>{dom.window.close();process.exit(0)},error=>{console.error(error);dom.window.close();process.exit(1)});
