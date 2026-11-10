# SPDX-License-Identifier: AGPL-3.0-or-later
"""Re-encode preserved graphics from the user's local stock image, without PIL."""
def repack(stock, offset, pixels):
    if offset<0 or not 0<pixels<=480*240:
        raise ValueError('Invalid local image bounds.')
    decoded=bytearray()
    while len(decoded)<pixels:
        if offset>=len(stock):raise ValueError('Truncated local image.')
        control=stock[offset];offset+=1;count=control>>1
        size=count if control&1 else 1
        if offset+size>len(stock):
            raise ValueError('Invalid local image stream.')
        # Stock includes zero-length packets and final runs extending past the
        # declared image size. Match the native decoder's pixel limit.
        take=min(count,pixels-len(decoded))
        decoded.extend(stock[offset:offset+take] if control&1 else stock[offset:offset+1]*take)
        offset+=size
    output=bytearray();literal=bytearray();i=0
    def flush():
        while literal:
            chunk=literal[:127];del literal[:127]
            output.append((len(chunk)<<1)|1);output.extend(chunk)
    while i<pixels:
        end=i
        while end<pixels and end-i<127 and decoded[end]==decoded[i]:end+=1
        count=end-i
        if count>=3 or (count==2 and not literal):
            flush();output.extend((count<<1,decoded[i]))
        else:literal.extend(decoded[i:end])
        i=end
    flush()
    return bytes(output)
