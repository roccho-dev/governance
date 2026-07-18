"""Minimal RFC 8032 Ed25519 verifier and deterministic test-vector signer.

Production signing is intentionally not exposed here; the publisher CLI uses a
separately installed, reviewed Ed25519 implementation. The reference signer is
only for deterministic fixtures and destructive tests.
"""
from __future__ import annotations

import hashlib

Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493

def inv(x: int) -> int: return pow(x, Q - 2, Q)
D = (-121665 * inv(121666)) % Q
I = pow(2, (Q - 1) // 4, Q)

def xrecover(y: int) -> int:
    xx=(y*y-1)*inv(D*y*y+1); x=pow(xx,(Q+3)//8,Q)
    if (x*x-xx)%Q!=0: x=(x*I)%Q
    if x%2!=0: x=Q-x
    return x

BY=(4*inv(5))%Q; BX=xrecover(BY); B=(BX,BY,1,(BX*BY)%Q)

def point_add(p: tuple[int,int,int,int], q: tuple[int,int,int,int]) -> tuple[int,int,int,int]:
    x1,y1,z1,t1=p; x2,y2,z2,t2=q
    a=((y1-x1)*(y2-x2))%Q; b=((y1+x1)*(y2+x2))%Q; c=(2*D*t1*t2)%Q; d=(2*z1*z2)%Q
    e=(b-a)%Q; f=(d-c)%Q; g=(d+c)%Q; h=(b+a)%Q
    return ((e*f)%Q,(g*h)%Q,(f*g)%Q,(e*h)%Q)

def point_mul(p: tuple[int,int,int,int], scalar: int) -> tuple[int,int,int,int]:
    result=(0,1,1,0); addend=p; n=scalar
    while n:
        if n&1: result=point_add(result,addend)
        addend=point_add(addend,addend); n>>=1
    return result

def encode_point(p: tuple[int,int,int,int]) -> bytes:
    x,y,z,_=p; zi=inv(z); x=(x*zi)%Q; y=(y*zi)%Q
    return int.to_bytes(y|((x&1)<<255),32,"little")

def is_on_curve(p: tuple[int,int,int,int]) -> bool:
    x,y,z,t=p
    return (x*y-z*t)%Q==0 and (y*y-x*x-z*z-D*t*t)%Q==0

def decode_point(data: bytes) -> tuple[int,int,int,int]:
    if len(data)!=32: raise ValueError("point-length")
    value=int.from_bytes(data,"little"); y=value&((1<<255)-1)
    if y>=Q: raise ValueError("point-y")
    x=xrecover(y)
    if (x&1)!=(value>>255): x=Q-x
    p=(x,y,1,(x*y)%Q)
    if not is_on_curve(p): raise ValueError("point-curve")
    return p

def hint(data: bytes) -> int: return int.from_bytes(hashlib.sha512(data).digest(),"little")

def secret_expand(seed: bytes) -> tuple[int,bytes]:
    if len(seed)!=32: raise ValueError("seed-length")
    h=bytearray(hashlib.sha512(seed).digest()); h[0]&=248; h[31]&=63; h[31]|=64
    return int.from_bytes(h[:32],"little"),bytes(h[32:])

def public_key_from_seed(seed: bytes) -> bytes:
    scalar,_=secret_expand(seed); return encode_point(point_mul(B,scalar))

def sign_reference(seed: bytes, message: bytes) -> bytes:
    """Reference-only deterministic signer for tests; not a production signer."""
    scalar,prefix=secret_expand(seed); public=public_key_from_seed(seed); r=hint(prefix+message)%L
    encoded_r=encode_point(point_mul(B,r)); h=hint(encoded_r+public+message)%L; s=(r+h*scalar)%L
    return encoded_r+int.to_bytes(s,32,"little")

def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    try:
        if len(public)!=32 or len(signature)!=64: return False
        encoded_r=signature[:32]; s=int.from_bytes(signature[32:],"little")
        if s>=L: return False
        a=decode_point(public); r=decode_point(encoded_r); h=hint(encoded_r+public+message)%L
        return encode_point(point_mul(B,s))==encode_point(point_add(r,point_mul(a,h)))
    except ValueError:
        return False
