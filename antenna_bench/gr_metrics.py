"""Small streaming blocks exposed through GRC Embedded Python wrappers.

All decisions and metric outputs are generated in the running flowgraph.
stop() writes exact integer counts/energies; GUI streams use float32 for display.
"""
import json
from pathlib import Path
import threading
import numpy as np
from gnuradio import gr
from antenna_bench.live import wlan_reference, recover_burst
from antenna_bench.math import binomial_interval, zero_error_upper_bound


class JsonStats:
    def set_report_path(self,path):
        self._report_path=str(path)

    def save(self):
        result=self.statistics()
        if self._report_path:
            path=Path(self._report_path); path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        return result

    def stop(self):
        self.save()
        return True


class BitErrorMeter(JsonStats, gr.sync_block):
    """Aligned TX/RX unpacked bits -> cumulative BER; exact counts in JSON."""
    def __init__(self, report_path='', run_config=None):
        gr.sync_block.__init__(self,name='SISO cumulative BER (TX bits vs RX bits)',
            in_sig=[np.uint8,np.uint8],out_sig=[np.float32])
        self._report_path=report_path; self._bits=0; self._errors=0; self._history=[]
        self._lock=threading.Lock()
        self._context=dict(run_config or {})

    def work(self,inputs,outputs):
        count=min(len(inputs[0]),len(inputs[1]),len(outputs[0]))
        if not count: return 0
        with self._lock:
            self._errors+=int(np.count_nonzero(inputs[0][:count]!=inputs[1][:count]))
            self._bits+=count
            outputs[0][:count]=self._errors/self._bits
            if len(self._history)<2000: self._history.append([self._bits,self._errors])
        return count

    def statistics(self):
        with self._lock:
            lo,hi=binomial_interval(self._errors,self._bits) if self._bits else (None,None)
            history=self._history.copy()
            if self._bits and (not history or history[-1][0]!=self._bits): history.append([self._bits,self._errors])
            return dict(context=self._context,bits=self._bits,errors=self._errors,ber=self._errors/self._bits if self._bits else None,
                ci95_lower=lo,ci95_upper=hi,
                zero_error_upper95=zero_error_upper_bound(self._bits) if self._bits and not self._errors else None,
                confidence_scope='nominal independent-bit bounds; QAM/coded bits can be correlated',
                history=history)


class EvmMeter(JsonStats, gr.sync_block):
    """Aligned clean/equalized symbols -> pooled RMS EVM percent, no fitting."""
    def __init__(self,report_path='',run_config=None):
        gr.sync_block.__init__(self,name='SISO reference EVM (%)',
            in_sig=[np.complex64,np.complex64],out_sig=[np.float32])
        self._report_path=report_path; self._symbols=0; self._error=0.; self._reference=0.
        self._lock=threading.Lock()
        self._context=dict(run_config or {})

    def work(self,inputs,outputs):
        count=min(len(inputs[0]),len(inputs[1]),len(outputs[0]))
        if not count: return 0
        tx=inputs[0][:count].astype(complex); rx=inputs[1][:count].astype(complex)
        with self._lock:
            self._symbols+=count; self._error+=float(np.sum(abs(rx-tx)**2))
            self._reference+=float(np.sum(abs(tx)**2))
            outputs[0][:count]=100*np.sqrt(self._error/self._reference)
        return count

    def statistics(self):
        with self._lock:
            evm=float(np.sqrt(self._error/self._reference)) if self._reference else None
            return dict(context=self._context,symbols=self._symbols,error_energy=self._error,reference_energy=self._reference,
                        evm_rms=evm,evm_percent=100*evm if evm is not None else None)


class BurstReceiver(JsonStats, gr.basic_block):
    """PPDU sample stream -> equalized DATA stream; known-boundary SISO receiver."""
    def __init__(self,rate_index=2,correct_cfo=True,pilot_tracking=True,report_path=''):
        self._reference=wlan_reference(int(rate_index))
        gr.basic_block.__init__(self,name='SISO STF/LTF CFO + LTF ZF + pilot phase + DATA FFT',
            in_sig=[np.complex64],out_sig=[np.complex64])
        self._cfo=bool(correct_cfo); self._pilot=bool(pilot_tracking); self._report_path=report_path
        self._frequencies=[]; self._bursts=0
        self._buffer=np.empty(self._reference['tx_packet'].size,dtype=np.complex64)
        self._fill=0; self._pending=np.empty(0,dtype=np.complex64); self._position=0

    def forecast(self,noutput_items,ninputs):
        return [0 if self._position<len(self._pending) else 1]*ninputs

    def general_work(self,inputs,outputs):
        if self._position==len(self._pending):
            count=min(len(inputs[0]),len(self._buffer)-self._fill)
            self._buffer[self._fill:self._fill+count]=inputs[0][:count]
            self._fill+=count; self.consume(0,count)
            if self._fill<len(self._buffer): return 0
            eq,frequency=recover_burst(self._buffer,self._reference,self._cfo,self._pilot)
            self._pending=eq.ravel(order='F').astype(np.complex64); self._position=0; self._fill=0
            self._bursts+=1
            if len(self._frequencies)<2000: self._frequencies.append(frequency)
        count=min(len(outputs[0]),len(self._pending)-self._position)
        outputs[0][:count]=self._pending[self._position:self._position+count]
        self._position+=count
        return count

    def statistics(self):
        return dict(bursts=self._bursts,timing='known fixed burst boundaries; no packet detection',
                    cfo_correction=self._cfo,pilot_tracking=self._pilot,
                    partial_input_samples=self._fill,pending_output_symbols=len(self._pending)-self._position,
                    estimated_cfo_hz=self._frequencies.copy())
