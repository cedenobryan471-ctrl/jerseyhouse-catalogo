const { test } = require('node:test');
const assert = require('node:assert/strict');
const { recoveryAction } = require('./gallery_retry.cjs');
const run = {head_branch:'main',event:'workflow_dispatch',conclusion:'failure',display_title:'Galerías automáticas',run_number:82};
test('three retries, then continue from saved progress', () => {
  assert.deepEqual([1,2,3,4].map(run_attempt => recoveryAction({...run,run_attempt})), ['retry','retry','retry','next']);
});
test('never act on running #81', () => {
  assert.equal(recoveryAction({...run,run_number:81,display_title:'Recuperar galerías sin IA',conclusion:null}), 'none');
});
test('handle legacy #81 only once it has failed', () => {
  assert.equal(recoveryAction({...run,run_number:81,display_title:'Recuperar galerías sin IA',run_attempt:1}), 'retry');
});
test('leave successful, canceled, pilot and older runs untouched', () => {
  for (const conclusion of ['success','cancelled',null]) assert.equal(recoveryAction({...run,conclusion}), 'none');
  for (const display_title of ['Galerías piloto','Galerías manuales']) assert.equal(recoveryAction({...run,display_title}), 'none');
  assert.equal(recoveryAction({...run,run_number:80,display_title:'Recuperar galerías sin IA'}), 'none');
});
