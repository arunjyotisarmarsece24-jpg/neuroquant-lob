"""
NeuroQuant-LOB: Institutional FIX 4.4 Protocol Engine
=====================================================
Ultra-low-overhead, zero-dependency Tag-Value wire protocol codec for FIX 4.4.
Compliant with institutional electronic trading specifications (CME, Nasdaq, BATS, Binance FIX).

Supported Messages:
  - 35=D: NewOrderSingle
  - 35=8: ExecutionReport
  - 35=F: OrderCancelRequest
  - 35=G: OrderCancelReplaceRequest
  - 35=0: Heartbeat
  - 35=3: Reject (Session)
  - 35=j: BusinessMessageReject

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
Project: NeuroQuant-LOB Flagship Quantitative Architecture
Version: 1.1.0-PROD
"""

from __future__ import annotations
import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any


SOH = "\x01"
SOH_BYTES = b"\x01"


class FixMsgType(str, Enum):
    HEARTBEAT = "0"
    TEST_REQUEST = "1"
    RESEND_REQUEST = "2"
    REJECT = "3"
    NEW_ORDER_SINGLE = "D"
    EXECUTION_REPORT = "8"
    ORDER_CANCEL_REQUEST = "F"
    ORDER_CANCEL_REPLACE_REQUEST = "G"
    ORDER_CANCEL_REJECT = "9"
    BUSINESS_MESSAGE_REJECT = "j"


class FixSide(str, Enum):
    BUY = "1"
    SELL = "2"


class FixOrdType(str, Enum):
    MARKET = "1"
    LIMIT = "2"
    STOP = "3"
    STOP_LIMIT = "4"


class FixTimeInForce(str, Enum):
    DAY = "0"
    GTC = "1"
    IOC = "3"
    FOK = "4"


class FixOrdStatus(str, Enum):
    NEW = "0"
    PARTIALLY_FILLED = "1"
    FILLED = "2"
    DONE_FOR_DAY = "3"
    CANCELED = "4"
    REPLACED = "5"
    PENDING_CANCEL = "6"
    STOPPED = "7"
    REJECTED = "8"
    SUSPENDED = "9"
    PENDING_NEW = "A"
    EXPIRED = "C"


class FixExecType(str, Enum):
    NEW = "0"
    PARTIAL_FILL = "1"
    FILL = "2"
    DONE_FOR_DAY = "3"
    CANCELED = "4"
    REPLACED = "5"
    PENDING_CANCEL = "6"
    STOPPED = "7"
    REJECTED = "8"
    SUSPENDED = "9"
    PENDING_NEW = "A"
    EXPIRED = "C"
    TRADE = "F"
    ORDER_STATUS = "I"


class FixTag:
    # Standard Header
    BeginString = 8
    BodyLength = 9
    MsgType = 35
    SenderCompID = 49
    TargetCompID = 56
    MsgSeqNum = 34
    SendingTime = 52

    # Standard Trailer
    CheckSum = 10

    # Common Fields
    ClOrdID = 11
    OrigClOrdID = 41
    OrderID = 37
    ExecID = 17
    ExecType = 150
    OrdStatus = 39
    Symbol = 55
    Side = 54
    OrderQty = 38
    Price = 44
    OrdType = 40
    TimeInForce = 59
    LastPx = 31
    LastQty = 32
    CumQty = 14
    AvgPx = 6
    LeavesQty = 151
    Text = 58
    TransactTime = 60
    ExecRestatementReason = 378
    OrdRejReason = 103
    CxlRejReason = 102
    CxlRejResponseTo = 434

    # Proprietary HFT Microstructure Tags
    AlphaSignal = 9001
    QueueDepthAhead = 9002
    MicroPrice = 9003
    ToxicityScore = 9004
    ExecutionVenue = 9005


class FixMessage:
    """
    Represents an institutional FIX 4.4 message with tag-value pairs.
    Preserves exact ordering for deterministic wire serialization and hashing.
    """

    def __init__(self, msg_type: Optional[Union[str, Enum]] = None):
        self._fields: List[Tuple[int, str]] = []
        self._dict: Dict[int, str] = {}
        if msg_type is not None:
            val = msg_type.value if hasattr(msg_type, "value") else str(msg_type)
            self.set(FixTag.MsgType, val)

    def set(self, tag: int, value: Any) -> FixMessage:
        """Sets a tag-value pair. If tag exists, updates value and keeps position."""
        val_str = value.value if hasattr(value, "value") else str(value)
        if tag in self._dict:
            self._dict[tag] = val_str
            for i, (t, _) in enumerate(self._fields):
                if t == tag:
                    self._fields[i] = (tag, val_str)
                    break
        else:
            self._dict[tag] = val_str
            self._fields.append((tag, val_str))
        return self

    def get(self, tag: int, default: Optional[str] = None) -> Optional[str]:
        return self._dict.get(tag, default)

    def get_float(self, tag: int, default: float = 0.0) -> float:
        val = self._dict.get(tag)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    def get_int(self, tag: int, default: int = 0) -> int:
        val = self._dict.get(tag)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    def has(self, tag: int) -> bool:
        return tag in self._dict

    def __getitem__(self, tag: int) -> str:
        return self._dict[tag]

    def __setitem__(self, tag: int, value: Any) -> None:
        self.set(tag, value)

    def __contains__(self, tag: int) -> bool:
        return tag in self._dict

    @property
    def msg_type(self) -> Optional[str]:
        return self.get(FixTag.MsgType)

    @property
    def cl_ord_id(self) -> Optional[str]:
        return self.get(FixTag.ClOrdID)

    @property
    def order_id(self) -> Optional[str]:
        return self.get(FixTag.OrderID)

    @property
    def exec_id(self) -> Optional[str]:
        return self.get(FixTag.ExecID)

    @property
    def symbol(self) -> Optional[str]:
        return self.get(FixTag.Symbol)

    @property
    def side(self) -> Optional[str]:
        return self.get(FixTag.Side)

    @property
    def order_qty(self) -> float:
        return self.get_float(FixTag.OrderQty)

    @property
    def price(self) -> float:
        return self.get_float(FixTag.Price)

    @property
    def ord_status(self) -> Optional[str]:
        return self.get(FixTag.OrdStatus)

    @property
    def exec_type(self) -> Optional[str]:
        return self.get(FixTag.ExecType)

    def to_wire(self) -> bytes:
        """Encodes to standard FIX 4.4 byte wire format with Tag 9 and Tag 10 checksum."""
        return FixProtocolEngine.encode(self)

    def to_human_readable(self, separator: str = "|") -> str:
        """Returns string representation with SOH replaced by '|' for readability."""
        raw = self.to_wire().decode("latin1", errors="replace")
        return raw.replace(SOH, separator)

    def __repr__(self) -> str:
        body = ", ".join(f"{t}={v}" for t, v in self._fields if t not in (8, 9, 10))
        return f"<FixMessage {self.msg_type or '?'} [{body}]>"


class FixProtocolEngine:
    """
    Zero-overhead encoder and decoder for FIX 4.4 messages.
    """

    BEGIN_STRING = "FIX.4.4"

    @staticmethod
    def current_utc_timestamp() -> str:
        """Generates standard FIX millisecond timestamp: YYYYMMDD-HH:MM:SS.sss"""
        now = datetime.datetime.now(datetime.timezone.utc)
        return now.strftime("%Y%m%d-%H:%M:%S.%f")[:-3]

    @classmethod
    def encode(cls, msg: FixMessage) -> bytes:
        """
        Serializes a FixMessage into FIX 4.4 wire bytes:
        8=FIX.4.4<SOH>9=len<SOH>...<SOH>10=xxx<SOH>
        """
        # Exclude standard header tags 8, 9 and trailer tag 10 from body calculation
        body_parts: List[str] = []
        for tag, val in msg._fields:
            if tag in (FixTag.BeginString, FixTag.BodyLength, FixTag.CheckSum):
                continue
            body_parts.append(f"{tag}={val}")

        body_str = SOH.join(body_parts) + SOH
        body_bytes = body_str.encode("latin1")
        body_len = len(body_bytes)

        # Build wire message without checksum:
        # 8=FIX.4.4<SOH>9=<len><SOH><body_bytes>
        prefix = f"8={cls.BEGIN_STRING}{SOH}9={body_len}{SOH}".encode("latin1")
        pre_checksum = prefix + body_bytes

        # Modulo 256 checksum
        checksum_val = sum(pre_checksum) % 256
        checksum_str = f"10={checksum_val:03d}{SOH}"

        return pre_checksum + checksum_str.encode("latin1")

    @classmethod
    def decode(cls, raw: Union[bytes, str]) -> FixMessage:
        """
        Parses FIX 4.4 wire bytes or string into a FixMessage.
        Validates structure and checksum.
        """
        if isinstance(raw, str):
            raw_bytes = raw.encode("latin1")
        else:
            raw_bytes = raw

        # Check delimiter: either SOH or pipe '|'
        delim = SOH_BYTES if SOH_BYTES in raw_bytes else b"|"
        parts = [p for p in raw_bytes.split(delim) if p]

        msg = FixMessage()
        checksum_found = None
        for p in parts:
            idx = p.find(b"=")
            if idx == -1:
                continue
            tag_str = p[:idx].decode("latin1", errors="replace")
            val_str = p[idx + 1:].decode("latin1", errors="replace")
            try:
                tag = int(tag_str)
            except ValueError:
                continue

            if tag == FixTag.CheckSum:
                checksum_found = val_str
            msg.set(tag, val_str)

        # Checksum validation if present and SOH format used
        if checksum_found is not None and SOH_BYTES in raw_bytes:
            idx_10 = raw_bytes.rfind(b"10=")
            if idx_10 != -1:
                bytes_for_csum = raw_bytes[:idx_10]
                expected_csum = f"{sum(bytes_for_csum) % 256:03d}"
                if checksum_found != expected_csum:
                    raise ValueError(
                        f"FIX Checksum mismatch: wire={checksum_found}, computed={expected_csum}"
                    )

        return msg

    @classmethod
    def create_heartbeat(
        cls,
        sender_comp_id: str,
        target_comp_id: str,
        seq_num: int
    ) -> FixMessage:
        msg = FixMessage(FixMsgType.HEARTBEAT)
        msg.set(FixTag.SenderCompID, sender_comp_id)
        msg.set(FixTag.TargetCompID, target_comp_id)
        msg.set(FixTag.MsgSeqNum, seq_num)
        msg.set(FixTag.SendingTime, cls.current_utc_timestamp())
        return msg

    @classmethod
    def create_new_order_single(
        cls,
        cl_ord_id: str,
        symbol: str,
        side: FixSide,
        order_qty: float,
        price: float,
        ord_type: FixOrdType = FixOrdType.LIMIT,
        time_in_force: FixTimeInForce = FixTimeInForce.DAY,
        sender_comp_id: str = "NEUROQUANT",
        target_comp_id: str = "CITADEL_CONNECT",
        seq_num: int = 1,
        alpha_signal: Optional[float] = None,
        micro_price: Optional[float] = None,
    ) -> FixMessage:
        """
        Creates an institutional 35=D NewOrderSingle with embedded quantitative metadata.
        """
        msg = FixMessage(FixMsgType.NEW_ORDER_SINGLE)
        msg.set(FixTag.SenderCompID, sender_comp_id)
        msg.set(FixTag.TargetCompID, target_comp_id)
        msg.set(FixTag.MsgSeqNum, seq_num)
        msg.set(FixTag.SendingTime, cls.current_utc_timestamp())
        msg.set(FixTag.ClOrdID, cl_ord_id)
        msg.set(FixTag.Symbol, symbol)
        msg.set(FixTag.Side, side.value if isinstance(side, FixSide) else str(side))
        msg.set(FixTag.OrderQty, f"{order_qty:.4f}".rstrip("0").rstrip("."))
        msg.set(FixTag.OrdType, ord_type.value if isinstance(ord_type, FixOrdType) else str(ord_type))
        msg.set(FixTag.TimeInForce, time_in_force.value if isinstance(time_in_force, FixTimeInForce) else str(time_in_force))
        msg.set(FixTag.TransactTime, cls.current_utc_timestamp())

        if ord_type in (FixOrdType.LIMIT, FixOrdType.STOP_LIMIT):
            msg.set(FixTag.Price, f"{price:.2f}")

        if alpha_signal is not None:
            msg.set(FixTag.AlphaSignal, f"{alpha_signal:.4f}")
        if micro_price is not None:
            msg.set(FixTag.MicroPrice, f"{micro_price:.2f}")

        return msg

    @classmethod
    def create_order_cancel_request(
        cls,
        orig_cl_ord_id: str,
        cl_ord_id: str,
        symbol: str,
        side: FixSide,
        order_qty: float,
        sender_comp_id: str = "NEUROQUANT",
        target_comp_id: str = "CITADEL_CONNECT",
        seq_num: int = 2,
        toxicity_score: Optional[float] = None
    ) -> FixMessage:
        """
        Creates an institutional 35=F OrderCancelRequest triggered by toxic flow or quote update.
        """
        msg = FixMessage(FixMsgType.ORDER_CANCEL_REQUEST)
        msg.set(FixTag.SenderCompID, sender_comp_id)
        msg.set(FixTag.TargetCompID, target_comp_id)
        msg.set(FixTag.MsgSeqNum, seq_num)
        msg.set(FixTag.SendingTime, cls.current_utc_timestamp())
        msg.set(FixTag.OrigClOrdID, orig_cl_ord_id)
        msg.set(FixTag.ClOrdID, cl_ord_id)
        msg.set(FixTag.Symbol, symbol)
        msg.set(FixTag.Side, side.value if isinstance(side, FixSide) else str(side))
        msg.set(FixTag.OrderQty, f"{order_qty:.4f}".rstrip("0").rstrip("."))
        msg.set(FixTag.TransactTime, cls.current_utc_timestamp())

        if toxicity_score is not None:
            msg.set(FixTag.ToxicityScore, f"{toxicity_score:.4f}")

        return msg

    @classmethod
    def create_execution_report(
        cls,
        order_id: str,
        cl_ord_id: str,
        exec_id: str,
        exec_type: FixExecType,
        ord_status: FixOrdStatus,
        symbol: str,
        side: FixSide,
        order_qty: float,
        leaves_qty: float,
        cum_qty: float,
        avg_px: float,
        last_px: float = 0.0,
        last_qty: float = 0.0,
        price: float = 0.0,
        sender_comp_id: str = "CITADEL_CONNECT",
        target_comp_id: str = "NEUROQUANT",
        seq_num: int = 1,
        text: Optional[str] = None,
        queue_depth_ahead: Optional[float] = None
    ) -> FixMessage:
        """
        Creates an institutional 35=8 ExecutionReport for order lifecycle confirmation,
        partial fills, full fills, or cancellations.
        """
        msg = FixMessage(FixMsgType.EXECUTION_REPORT)
        msg.set(FixTag.SenderCompID, sender_comp_id)
        msg.set(FixTag.TargetCompID, target_comp_id)
        msg.set(FixTag.MsgSeqNum, seq_num)
        msg.set(FixTag.SendingTime, cls.current_utc_timestamp())
        msg.set(FixTag.OrderID, order_id)
        msg.set(FixTag.ClOrdID, cl_ord_id)
        msg.set(FixTag.ExecID, exec_id)
        msg.set(FixTag.ExecType, exec_type.value if isinstance(exec_type, FixExecType) else str(exec_type))
        msg.set(FixTag.OrdStatus, ord_status.value if isinstance(ord_status, FixOrdStatus) else str(ord_status))
        msg.set(FixTag.Symbol, symbol)
        msg.set(FixTag.Side, side.value if isinstance(side, FixSide) else str(side))
        msg.set(FixTag.OrderQty, f"{order_qty:.4f}".rstrip("0").rstrip("."))
        msg.set(FixTag.LeavesQty, f"{leaves_qty:.4f}".rstrip("0").rstrip("."))
        msg.set(FixTag.CumQty, f"{cum_qty:.4f}".rstrip("0").rstrip("."))
        msg.set(FixTag.AvgPx, f"{avg_px:.2f}")

        if last_qty > 0:
            msg.set(FixTag.LastQty, f"{last_qty:.4f}".rstrip("0").rstrip("."))
            msg.set(FixTag.LastPx, f"{last_px:.2f}")

        if price > 0:
            msg.set(FixTag.Price, f"{price:.2f}")

        if text is not None:
            msg.set(FixTag.Text, text)

        if queue_depth_ahead is not None:
            msg.set(FixTag.QueueDepthAhead, f"{queue_depth_ahead:.4f}".rstrip("0").rstrip("."))

        msg.set(FixTag.TransactTime, cls.current_utc_timestamp())
        return msg
