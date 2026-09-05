#!/usr/bin/env -S uv run --script
"""
Convert Windows SID to byte array format
Supports any SID structure: S-1-5-21-... or other SID formats
"""

def sid_to_bytes(sid_string):
    """
    Convert any Windows SID to byte array format
    
    Args:
        sid_string (str): Windows SID (e.g., 'S-1-5-21-2327345182-1863223493-3435513819')
    
    Returns:
        tuple: (comma_separated_bytes, continuous_hex_string)
    """
    
    # Parse SID components
    if not sid_string.startswith('S-'):
        raise ValueError("Invalid SID format - must start with 'S-'")
    
    # Split all components
    parts = sid_string.split('-')
    
    # First part should be 'S'
    if parts[0] != 'S':
        raise ValueError("Invalid SID format - first part must be 'S'")
    
    # Extract SID components
    revision = int(parts[1])  # Usually 1
    identifier_authority = int(parts[2])  # Usually 5 for NT Authority
    
    # The remaining parts are subauthorities (variable length)
    subauthorities = [int(x) for x in parts[3:]]
    
    # Build the SID structure
    # Format: [Revision][SubAuthorityCount][IdentifierAuthority(6 bytes)][SubAuthorities(variable)]
    
    result_bytes = []
    raw_bytes = []
    
    # 1. Revision (1 byte)
    result_bytes.append(f"0x{revision:02X}")
    raw_bytes.append(revision)
    
    # 2. SubAuthority Count (1 byte)
    result_bytes.append(f"0x{len(subauthorities):02X}")
    raw_bytes.append(len(subauthorities))
    
    # 3. Identifier Authority (6 bytes - big endian)
    # For values <= 0xFFFFFFFF, pad with zeros
    auth_bytes = identifier_authority.to_bytes(6, byteorder='big')
    for b in auth_bytes:
        result_bytes.append(f"0x{b:02X}")
        raw_bytes.append(b)
    
    # 4. SubAuthorities (4 bytes each - little endian)
    for subauth in subauthorities:
        # Convert to 4 bytes little endian
        subauth_bytes = subauth.to_bytes(4, byteorder='little')
        for b in subauth_bytes:
            result_bytes.append(f"0x{b:02X}")
            raw_bytes.append(b)
    
    # Create comma-separated format
    comma_format = ', '.join(result_bytes)
    
    # Create continuous hex string format (with 0x prefix)
    hex_string = '0x' + ''.join([f"{b:02X}" for b in raw_bytes])
    
    return comma_format, hex_string


def sid_to_bytes_alternative(sid_string):
    """
    Alternative version - maintains your original formatting style
    More flexible with different SID structures
    """
    
    # Parse SID
    parts = sid_string.split('-')
    
    if parts[0] != 'S':
        raise ValueError("Invalid SID format")
    
    # Get revision and authority
    revision = int(parts[1])
    authority = int(parts[2])
    subauthorities = [int(x) for x in parts[3:]]
    
    # Build the byte array
    byte_array = []
    raw_bytes = []
    
    # Add revision
    byte_array.append(f"0x{revision:02X}")
    raw_bytes.append(revision)
    
    # Add subauthority count
    byte_array.append(f"0x{len(subauthorities):02X}")
    raw_bytes.append(len(subauthorities))
    
    # Add authority (6 bytes, big endian)
    auth_hex = format(authority, '012x')  # 6 bytes = 12 hex chars
    for i in range(0, 12, 2):
        byte_val = int(auth_hex[i:i+2], 16)
        byte_array.append(f"0x{auth_hex[i:i+2].upper()}")
        raw_bytes.append(byte_val)
    
    # Add subauthorities (4 bytes each, little endian)
    for subauth in subauthorities:
        # Convert to 4-byte little endian
        hex_val = format(subauth, '08x')
        # Reverse for little endian
        little_endian = [hex_val[i:i+2] for i in range(6, -2, -2)]
        for byte in little_endian:
            byte_array.append(f"0x{byte.upper()}")
            raw_bytes.append(int(byte, 16))
    
    # Create comma-separated format
    comma_format = ', '.join(byte_array)
    
    # Create continuous hex string format (with 0x prefix)
    hex_string = '0x' + ''.join([f"{b:02X}" for b in raw_bytes])
    
    return comma_format, hex_string


def test_with_examples():
    """Test function with various SID examples"""
    
    test_sids = [
        'S-1-5-21-2327345182-1863223493-3435513819',  # Domain SID
        'S-1-5-18',                                    # Local System
        'S-1-5-19',                                    # Local Service
        'S-1-5-20',                                    # Network Service
        'S-1-0-0',                                     # Null SID
        'S-1-1-0',                                     # World
        'S-1-2-0',                                     # Local
        'S-1-3-0',                                     # Creator Owner
        'S-1-5-21-1275210071-1715567821-725345543-512' # Domain Admins
    ]
    
    print("=" * 80)
    print("SID to Byte Array Converter")
    print("=" * 80)
    
    for sid in test_sids:
        print(f"\nSID: {sid}")
        try:
            comma_format, hex_string = sid_to_bytes(sid)
            print(f"Comma format: {comma_format}")
            print(f"Hex string:   {hex_string}")
            byte_count = len(comma_format.split(','))
            print(f"Total bytes: {byte_count}")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n" + "=" * 80)


def main():
    """Main function with user input"""
    print("Windows SID to Byte Array Converter")
    print("-" * 60)
    print("Enter a SID (e.g., S-1-5-21-2327345182-1863223493-3435513819)")
    print("Or type 'test' to run examples")
    print("Or type 'quit' to exit")
    print("-" * 60)
    
    while True:
        user_input = input("\nSID: ").strip()
        
        if user_input.lower() == 'quit':
            print("Goodbye!")
            break
        elif user_input.lower() == 'test':
            test_with_examples()
        elif user_input:
            try:
                comma_format, hex_string = sid_to_bytes(user_input)
                print(f"\nComma format: {comma_format}")
                print(f"Hex string:   {hex_string}")
                
                # Also show byte count
                byte_count = len(comma_format.split(','))
                print(f"Total bytes: {byte_count}")
                
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("Please enter a SID")


if __name__ == "__main__":
    main()
