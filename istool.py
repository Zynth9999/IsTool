import os
import sys
import platform
import time
import random
import subprocess
import plistlib

class SerialGenerator:
    def __init__(self):
        self.name = "OpenCore Serial Generator"
        self.line_count = 0
        self.max_lines = 24

    def head(self, text=None, width=55):
        self.cls()
        if text is None:
            text = self.name
        print("  {}".format("#"*width))
        mid_len = int(round(width/2-len(text)/2)-2)
        middle = " #{}{}{}#".format(" "*mid_len, text, " "*((width - mid_len - len(text))-2))
        if len(middle) > width+1:
            di = len(middle) - width
            di += 3
            middle = middle[:-di] + "...#"
        print(middle)
        print("#"*width)
        self.line_count += 3

    def cls(self):
        """Clear screen and reset line count"""
        if platform.system() == "Darwin":
            os.system("clear")
        else:
            os.system("cls")
        self.line_count = 0

    def print(self, text):
        """Print text with line counting and auto-clear if needed"""
        if self.line_count >= self.max_lines:
            self.cls()
            self.head()
        print(text)
        self.line_count += 1

    def checkRequirements(self):
        """Verify all required modules are available"""
        self.head("Checking Requirements")
        try:
            import plistlib
            import subprocess
            import random
            import time
            import os
            import sys
            import platform
            self.print("✓ All required modules available")
            return True
        except ImportError:
            self.print("✗ Required modules are missing. Ensure Python 3.6 or higher is installed.")
            sys.exit(1)

    def checkForMacserial(self):
        """Verify macserial is available, download if necessary"""
        self.head("Checking for macserial")
        homeDirectory = os.path.expanduser("~")
        opencoreDirectory = os.path.join(homeDirectory, "OpenCorePkg")
        macserialPath = os.path.join(opencoreDirectory, "Utilities", "macserial", "macserial")
        
        if not os.path.exists(macserialPath):
            self.print("macserial not found.")
            self.print("Downloading OpenCorePkg...")
            
            if platform.system() == "Darwin":
                try:
                    subprocess.run(["git", "clone", "--depth", "1", "https://github.com/acidanthera/OpenCorePkg.git", opencoreDirectory], 
                                 check=True, capture_output=True)
                    
                    macserialDirectory = os.path.join(opencoreDirectory, "Utilities", "macserial")
                    if os.path.exists(macserialDirectory):
                        buildResult = subprocess.run(["make"], cwd=macserialDirectory, capture_output=True, text=True)
                        if buildResult.returncode != 0:
                            self.print("Failed to build macserial. Xcode command line tools may be required.")
                            self.print(f"Build error: {buildResult.stderr}")
                            return False
                    self.print("✓ OpenCorePkg downloaded and macserial built successfully.")
                    return True
                except subprocess.CalledProcessError as error:
                    self.print(f"✗ Failed to download OpenCorePkg: {error}")
                    return False
            else:
                self.print("✗ Unsupported platform. This script requires macOS.")
                return False
        else:
            self.print("✓ macserial found.")
            return True

    def generateSerialInfo(self):
        """Generate serial number, MLB, MAC address, ROM, and UUID"""
        self.head("Generating Serial Info")
        model = input("Enter SystemProductName from config.plist (e.g., iMac19,1): ").strip()
        
        homeDirectory = os.path.expanduser("~")
        macserialPath = os.path.join(homeDirectory, "OpenCorePkg", "Utilities", "macserial", "macserial")
        
        if not os.path.exists(macserialPath):
            self.print("✗ macserial not found. Verify OpenCorePkg installation.")
            sys.exit(1)
        
        try:
            result = subprocess.run([macserialPath, "--num", "1", "--model", model], 
                                  capture_output=True, text=True, check=True)
            serialOutput = result.stdout
            
            lines = serialOutput.strip().splitlines()
            
            serialNumber = None
            mlbNumber = None
            
            for line in lines:
                cleanLine = line.strip()
                if cleanLine and not cleanLine.startswith('#') and '|' in cleanLine:
                    parts = [part.strip() for part in cleanLine.split('|')]
                    if len(parts) >= 2:
                        serialNumber = parts[0]
                        mlbNumber = parts[1]
                        break
            
            if not serialNumber:
                for line in lines:
                    cleanLine = line.strip()
                    if cleanLine and not cleanLine.startswith('#') and len(cleanLine.split()) >= 2:
                        parts = cleanLine.split()
                        serialNumber = parts[0]
                        mlbNumber = parts[1]
                        break
            
            if not serialNumber:
                for line in lines:
                    cleanLine = line.strip()
                    if cleanLine and '|' in cleanLine:
                        parts = [part.strip() for part in cleanLine.split('|')]
                        if len(parts) >= 2:
                            serialNumber = parts[0]
                            mlbNumber = parts[1]
                            break
            
            if not serialNumber or not mlbNumber:
                self.print("✗ Failed to parse serial number and MLB from macserial output.")
                self.print(f"macserial output: {serialOutput}")
                sys.exit(1)
                
        except subprocess.CalledProcessError as error:
            self.print(f"✗ Error executing macserial: {error}")
            sys.exit(1)
        
        macAddress = "00:16:CB:{:02X}:{:02X}:{:02X}".format(
            random.randint(0, 255), 
            random.randint(0, 255), 
            random.randint(0, 255)
        )
        
        romValue = macAddress.replace(":", "").lower()
        
        try:
            uuidValue = subprocess.run(["uuidgen"], capture_output=True, text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError:
            import uuid as uuidLibrary
            uuidValue = str(uuidLibrary.uuid4()).upper()
        
        return serialNumber, mlbNumber, macAddress, romValue, uuidValue

    def updateConfigFile(self, configPath, serialNumber, mlbNumber, romValue, uuidValue):
        """Update config.plist with generated values"""
        self.head("Updating Config File")
        try:
            with open(configPath, 'rb') as file:
                configData = plistlib.load(file)
            
            if 'PlatformInfo' not in configData:
                configData['PlatformInfo'] = {}
            if 'Generic' not in configData['PlatformInfo']:
                configData['PlatformInfo']['Generic'] = {}
            
            configData['PlatformInfo']['Generic']['MLB'] = mlbNumber
            configData['PlatformInfo']['Generic']['SystemSerialNumber'] = serialNumber
            configData['PlatformInfo']['Generic']['SystemUUID'] = uuidValue
            
            try:
                romBytes = bytes.fromhex(romValue)
                configData['PlatformInfo']['Generic']['ROM'] = romBytes
            except ValueError as error:
                self.print(f"⚠️ Error converting ROM value: {error}")
                self.print("ROM value was not updated.")
            
            with open(configPath, 'wb') as file:
                plistlib.dump(configData, file)
            
            self.print("✓ config.plist updated successfully.")
            return True
            
        except Exception as error:
            self.print(f"✗ Error updating config file: {error}")
            return False

    def cleanDragAndDropPath(self, path):
        """Clean path from drag and drop input, handling escaped spaces"""
        cleanedPath = path.strip().strip('"')
        cleanedPath = cleanedPath.replace('\\ ', ' ')
        return cleanedPath

    def main(self):
        """Main execution function"""
        self.checkRequirements()

        self.cls()
        self.head("OpenCore Serial Generator")
        
        if not self.checkForMacserial():
            self.print("✗ Failed to initialize macserial. Exiting.")
            sys.exit(1)
        
        serialNumber, mlbNumber, macAddress, romValue, uuidValue = self.generateSerialInfo()
        
        self.head("Generated Values")
        self.print(f"Serial Number: {serialNumber}")
        self.print(f"MLB: {mlbNumber}")
        self.print(f"MAC Address: {macAddress}")
        self.print(f"ROM: {romValue}")
        self.print(f"UUID: {uuidValue}")
        self.print(f"Copy the Serial Number to check coverage.")
        self.print("\nOpening Apple coverage verification page...")
        time.sleep(2)
        
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", "https://checkcoverage.apple.com/?locale=en_US"])
            else:
                self.print("Manually visit: https://checkcoverage.apple.com/?locale=en_US")
        except:
            self.print("Could not open browser. Visit: https://checkcoverage.apple.com/?locale=en_US")
        
        prompt = """
Select the Apple coverage check result:
1. Unable to check coverage for this serial number
2. Valid Purchase Date / Coverage Expired
3. Purchase Date not Valsidated/Unavailable
"""
        self.print(prompt)
        
        userResponse = input("Enter selection (1, 2, or 3): ").strip()
        
        if userResponse == "1":
            self.print("✓ Serial number is valid for Hackintosh use.")
        elif userResponse == "2":
            self.print("✗ Serial number is already registered with Apple.")
            retry = input("Generate new serial number? (y/n): ").lower().strip()
            if retry == 'y':
                return self.main()
            else:
                self.print("Exiting.")
                sys.exit(0)
        elif userResponse == "3":
            self.print("⚠️ Serial number may work but could cause issues.")
        else:
            self.print("⚠️ Invalid response. Continuing.")
        
        # Pause
        input("Press Enter to continue...")
        self.head("Update Config.plist")
        self.print("Drag and drop your config.plist file here, then press Enter:")
        configPath = input().strip()
        
        configPath = self.cleanDragAndDropPath(configPath)
        
        if not os.path.exists(configPath):
            self.print(f"✗ Config file not found at: {configPath}")
            self.print("Exiting.")
            sys.exit(1)
        
        if self.updateConfigFile(configPath, serialNumber, mlbNumber, romValue, uuidValue):
            self.head("Complete")
            self.print("✓ Configuration update completed.")
        else:
            self.head("Error")
            self.print("✗ Configuration update failed. Manual update required.")

        # Print changes
        self.print("\nChanges Made:")
        self.print("\nKEY                  | NEW VALUE")
        self.print("-----------------------------------------------")
        self.print(f"SystemSerialNumber    | {serialNumber}")
        self.print(f"MLB                   | {mlbNumber}")
        self.print(f"ROM                   | {romValue}")
        self.print(f"UUID                  | {uuidValue}")

        # Ask to restart machine
        self.print("\nIt is recommended to restart your machine for changes to take effect.")
        restart = input("Restart now? (y/n): ").lower().strip()
        if restart == 'y':
            self.print("Restarting machine...")
            time.sleep(2)
            if platform.system() == "Darwin":
                subprocess.run(["sudo", "shutdown", "-r", "now"])

        else:
            self.print("Please remember to restart your machine later.")
            # Thank you message
            self.print("\nThank you for using iSTool!")
            time.sleep(2)
            # Exit
            sys.exit(0)

if __name__ == "__main__":
    generator = SerialGenerator()

    generator.head("DISCLAIMER")
    generator.print("I am not responsible for any damage or issues caused by using this tool.")
    generator.print("Use at your own risk.")
    generator.print("\nBy using this tool, you agree to the terms above.")
    generator.print("Press Enter to continue or Ctrl+C to exit.")
    input()

    

    generator.main()