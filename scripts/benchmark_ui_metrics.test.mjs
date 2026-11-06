import {test} from 'node:test'
import assert from 'node:assert/strict'
import {percentile, budgets} from './benchmark_ui_metrics.mjs'
test('budgets enforce absolute or matched improvement limits and preserve regressions', () => {
 assert.equal(percentile(Array.from({length:30},(_,i)=>i+1),.95),29)
 assert.equal(budgets({search:{p95:200}}).search.passed,true)
 assert.equal(budgets({search:{p95:201}}).search.passed,false)
 assert.equal(budgets({search:{p95:210}},{search:{p95:300}}).search.passed,true)
 assert.equal(budgets({search:{p95:211}},{search:{p95:300}}).search.passed,false)
 assert.equal(budgets({search:{p95:150}},{search:{p95:100}}).search.changePercent,50)
 assert.throws(()=>budgets({search:{p95:1}},{}),/Incomplete/)
 assert.throws(()=>percentile([], .95),/Invalid/)
})
