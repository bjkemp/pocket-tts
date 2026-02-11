#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>

@interface PocketTTSManager : NSObject <NSApplicationDelegate>
@property (strong) NSStatusItem *statusItem;
@property (strong) NSTimer *timer;
@property (assign) BOOL isRunning;
@property (assign) BOOL headphonesOnly;
@property (assign) BOOL isMuted;
@property (assign) BOOL isError; // New property to track errors
@property (strong) NSString *projectPath;
@property (strong) NSArray *voices;
@property (strong) NSString *currentVoice;
@property (strong) NSArray *personas;
@property (strong) NSString *currentPersona;
@end

@implementation PocketTTSManager

- (instancetype)init {
    self = [super init];
    if (self) {
        // Try to find project path dynamically
        NSString *bundlePath = [[NSBundle mainBundle] bundlePath];
        NSString *path = [bundlePath stringByDeletingLastPathComponent]; // build/
        path = [path stringByDeletingLastPathComponent]; // PocketMenuBar/
        path = [path stringByDeletingLastPathComponent]; // root
        
        NSString *checkPath = [path stringByAppendingPathComponent:@"pocket-say"];
        if (![[NSFileManager defaultManager] fileExistsAtPath:checkPath]) {
            path = @"/Users/kempb/Projects/pocket-tts";
        }
        
        _projectPath = path;
        _currentVoice = @"azelma";
        _currentPersona = @"narrator";
        
        // Load settings and error state immediately
        [self loadSettings];
        [self checkError];
        
        // Initialize placeholders so the menu works immediately
        _voices = @[@"alba", @"marius", @"javert", @"jean", @"fantine", @"cosette", @"eponine", @"azelma"];
        _personas = @[@"narrator"];
    }
    return self;
}

- (void)loadDynamicVoices {
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        NSString *scriptPath = [self.projectPath stringByAppendingPathComponent:@"scripts/list_all_voices.sh"];
        NSTask *task = [[NSTask alloc] init];
        [task setLaunchPath:@"/bin/bash"];
        [task setArguments:@[scriptPath]];
        
        NSPipe *pipe = [NSPipe pipe];
        [task setStandardOutput:pipe];
        
        NSError *taskError = nil;
        if (@available(macOS 10.13, *)) {
            [task launchAndReturnError:&taskError];
        } else {
            [task launch];
        }
        
        NSData *data = [[pipe fileHandleForReading] readDataToEndOfFile];
        [task waitUntilExit];
        
        NSString *output = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
        NSArray *lines = [output componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]];
        
        NSMutableArray *validVoices = [NSMutableArray array];
        for (NSString *line in lines) {
            NSString *trimmed = [line stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
            if (trimmed.length > 0) {
                [validVoices addObject:trimmed];
            }
        }
        
        dispatch_async(dispatch_get_main_queue(), ^{
            NSArray *defaultVoiceNames = @[@"alba", @"marius", @"javert", @"jean", @"fantine", @"cosette", @"eponine", @"azelma"];
            NSMutableArray *others = [NSMutableArray array];
            NSMutableArray *defaultsFound = [NSMutableArray array];
            
            for (NSString *voice in validVoices) {
                if ([defaultVoiceNames containsObject:voice.lowercaseString]) {
                    [defaultsFound addObject:voice];
                } else {
                    [others addObject:voice];
                }
            }
            
            // Sort both lists
            [defaultsFound sortUsingSelector:@selector(localizedCaseInsensitiveCompare:)];
            [others sortUsingSelector:@selector(localizedCaseInsensitiveCompare:)];
            
            // Combine: defaults first, then others
            NSMutableArray *finalList = [NSMutableArray arrayWithArray:defaultsFound];
            [finalList addObjectsFromArray:others];
            
            self.voices = finalList;
            [self setupMenu];
        });
    });
}

- (void)loadDynamicPersonas {
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        NSString *personasPath = [self.projectPath stringByAppendingPathComponent:@"personas"];
        NSError *error = nil;
        NSArray *files = [[NSFileManager defaultManager] contentsOfDirectoryAtPath:personasPath error:&error];
        
        NSMutableArray *validPersonas = [NSMutableArray array];
        for (NSString *file in files) {
            if ([file hasSuffix:@".md"]) {
                [validPersonas addObject:[file stringByDeletingPathExtension]];
            }
        }
        
        dispatch_async(dispatch_get_main_queue(), ^{
            self.personas = [validPersonas sortedArrayUsingSelector:@selector(localizedCaseInsensitiveCompare:)];
            [self setupMenu];
        });
    });
}

- (void)refreshLists {
    [self loadDynamicVoices];
    [self loadDynamicPersonas];
}

- (void)applicationDidFinishLaunching:(NSNotification *)aNotification {
    self.statusItem = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];
    [self updateIcon];
    [self setupMenu];
    
    // Start background loading
    [self refreshLists];
    [self checkStatus];
    
    // Poll status every 5 seconds
    self.timer = [NSTimer scheduledTimerWithTimeInterval:5.0 
                                                  target:self 
                                                selector:@selector(checkStatus) 
                                                userInfo:nil 
                                                 repeats:YES];
}



- (void)loadSettings {
    // Load Voice
    NSString *voicePath = [self.projectPath stringByAppendingPathComponent:@".current_voice"];
    NSError *error;
    NSString *voice = [NSString stringWithContentsOfFile:voicePath encoding:NSUTF8StringEncoding error:&error];
    if (voice) {
        _currentVoice = [voice stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    }

    // Load Persona
    NSString *personaPath = [self.projectPath stringByAppendingPathComponent:@".current_persona"];
    NSString *persona = [NSString stringWithContentsOfFile:personaPath encoding:NSUTF8StringEncoding error:&error];
    if (persona) {
        _currentPersona = [persona stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    }

    // Load Headphones Only setting
    NSString *hpPath = [self.projectPath stringByAppendingPathComponent:@".headphones_only"];
    _headphonesOnly = [[NSFileManager defaultManager] fileExistsAtPath:hpPath];

    // Load Mute setting
    NSString *mutePath = [self.projectPath stringByAppendingPathComponent:@".muted"];
    _isMuted = [[NSFileManager defaultManager] fileExistsAtPath:mutePath];
}

- (void)saveSettings {
    // Save Voice
    NSString *voicePath = [self.projectPath stringByAppendingPathComponent:@".current_voice"];
    [self.currentVoice writeToFile:voicePath atomically:YES encoding:NSUTF8StringEncoding error:nil];

    // Save Persona
    NSString *personaPath = [self.projectPath stringByAppendingPathComponent:@".current_persona"];
    [self.currentPersona writeToFile:personaPath atomically:YES encoding:NSUTF8StringEncoding error:nil];

    // Save Headphones Only setting
    NSString *hpPath = [self.projectPath stringByAppendingPathComponent:@".headphones_only"];
    if (self.headphonesOnly) {
        [@"1" writeToFile:hpPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    } else {
        [[NSFileManager defaultManager] removeItemAtPath:hpPath error:nil];
    }

    // Save Mute setting
    NSString *mutePath = [self.projectPath stringByAppendingPathComponent:@".muted"];
    if (self.isMuted) {
        [@"1" writeToFile:mutePath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    } else {
        [[NSFileManager defaultManager] removeItemAtPath:mutePath error:nil];
    }
}

- (void)checkError {
    NSString *errorPath = [self.projectPath stringByAppendingPathComponent:@".error"];
    self.isError = [[NSFileManager defaultManager] fileExistsAtPath:errorPath];
}

- (void)clearError {
    NSString *errorPath = [self.projectPath stringByAppendingPathComponent:@".error"];
    [[NSFileManager defaultManager] removeItemAtPath:errorPath error:nil];
    [self checkError];
    [self setupMenu];
    [self updateIcon];
}

- (void)setupMenu {
    [self checkError]; // Ensure we have latest state
    NSMenu *menu = [[NSMenu alloc] init];
    
    NSString *statusTitle = self.isRunning ? @"Status: Running" : @"Status: Stopped";
    NSMenuItem *statusItem = [[NSMenuItem alloc] initWithTitle:statusTitle action:nil keyEquivalent:@""];
    [statusItem setEnabled:NO];
    [menu addItem:statusItem];
    
    [menu addItem:[NSMenuItem separatorItem]];
    
    if (self.isRunning) {
        [menu addItemWithTitle:@"Stop Service" action:@selector(stopService) keyEquivalent:@"s"];
    } else {
        [menu addItemWithTitle:@"Start Service" action:@selector(startService) keyEquivalent:@"S"];
    }
    
    [menu addItem:[NSMenuItem separatorItem]];

    NSMenuItem *testItem = [[NSMenuItem alloc] initWithTitle:@"Test Voice" action:@selector(testVoice) keyEquivalent:@"t"];
    [testItem setEnabled:self.isRunning && !self.isError]; // Disable if there's an error
    [testItem setTarget:self];
    [menu addItem:testItem];

    if (self.isError) {
        NSMenuItem *clearErrorItem = [[NSMenuItem alloc] initWithTitle:@"Clear Error" action:@selector(clearError) keyEquivalent:@""];
        [clearErrorItem setTarget:self];
        [menu addItem:clearErrorItem];
    }

    NSMenuItem *muteItem = [[NSMenuItem alloc] initWithTitle:@"Mute" action:@selector(toggleMute:) keyEquivalent:@"m"];
    [muteItem setState:self.isMuted ? NSControlStateValueOn : NSControlStateValueOff];
    [muteItem setTarget:self];
    [menu addItem:muteItem];

    NSMenuItem *hpItem = [[NSMenuItem alloc] initWithTitle:@"Headphones Only" action:@selector(toggleHeadphonesOnly:) keyEquivalent:@"h"];
    [hpItem setState:self.headphonesOnly ? NSControlStateValueOn : NSControlStateValueOff];
    [hpItem setTarget:self];
    [menu addItem:hpItem];

    NSMenuItem *refreshItem = [[NSMenuItem alloc] initWithTitle:@"Refresh Lists" action:@selector(refreshLists) keyEquivalent:@"r"];
    [refreshItem setTarget:self];
    [menu addItem:refreshItem];
    
    [menu addItem:[NSMenuItem separatorItem]];
    
    NSMenu *voiceMenu = [[NSMenu alloc] init];
    for (NSString *voice in self.voices) {
        NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:voice action:@selector(selectVoice:) keyEquivalent:@""];
        [item setTarget:self];
        if ([voice isEqualToString:self.currentVoice]) {
            [item setState:NSControlStateValueOn];
        }
        [voiceMenu addItem:item];
    }
    
    NSMenuItem *voiceSubmenu = [[NSMenuItem alloc] initWithTitle:@"Default Voice" action:nil keyEquivalent:@""];
    [voiceSubmenu setSubmenu:voiceMenu];
    [menu addItem:voiceSubmenu];

    NSMenu *personaMenu = [[NSMenu alloc] init];
    for (NSString *persona in self.personas) {
        NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:persona action:@selector(selectPersona:) keyEquivalent:@""];
        [item setTarget:self];
        if ([persona isEqualToString:self.currentPersona]) {
            [item setState:NSControlStateValueOn];
        }
        [personaMenu addItem:item];
    }
    
    NSMenuItem *personaSubmenu = [[NSMenuItem alloc] initWithTitle:@"Default Persona" action:nil keyEquivalent:@""];
    [personaSubmenu setSubmenu:personaMenu];
    [menu addItem:personaSubmenu];
    
    [menu addItem:[NSMenuItem separatorItem]];
    [menu addItemWithTitle:@"Quit" action:@selector(terminate:) keyEquivalent:@"q"];
    
    self.statusItem.menu = menu;
}

- (void)toggleHeadphonesOnly:(NSMenuItem *)sender {
    self.headphonesOnly = !self.headphonesOnly;
    [self saveSettings];
    [self setupMenu];
}

- (void)toggleMute:(NSMenuItem *)sender {
    self.isMuted = !self.isMuted;
    [self saveSettings];
    [self setupMenu];
}

- (void)testVoice {
    NSString *cmd = [NSString stringWithFormat:@"cd %@ && ./PocketMenuBar/control.sh test", self.projectPath];
    NSTask *task = [[NSTask alloc] init];
    [task setLaunchPath:@"/bin/bash"];
    [task setArguments:@[@"-c", cmd]];
    [task launch];
}

- (void)updateIcon {
    if (self.isError) {
        self.statusItem.button.title = @"⚠️"; // Error icon
    } else {
        self.statusItem.button.title = self.isRunning ? @"🎙️" : @"🚫";
    }
}

- (void)checkStatus {
    NSURL *url = [NSURL URLWithString:@"http://localhost:8000/health"];
    NSURLSessionDataTask *task = [[NSURLSession sharedSession] dataTaskWithURL:url completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        BOOL wasRunning = self.isRunning;
        self.isRunning = (error == nil && [(NSHTTPURLResponse *)response statusCode] == 200);
        
        if (wasRunning != self.isRunning) {
            dispatch_async(dispatch_get_main_queue(), ^{
                [self setupMenu];
                [self updateIcon];
            });
        }
        [self checkError]; // Also check for error status periodically
    }];
    [task resume];
}

- (void)startService {
    NSString *cmd = [NSString stringWithFormat:@"cd %@ && ./scripts/start_server.sh", self.projectPath];
    NSTask *task = [[NSTask alloc] init];
    [task setLaunchPath:@"/bin/bash"];
    [task setArguments:@[@"-c", cmd]];
    [task launch];
    
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [self checkStatus];
    });
}

- (void)stopService {
    NSTask *task = [[NSTask alloc] init];
    [task setLaunchPath:@"/usr/bin/pkill"];
    [task setArguments:@[@"-f", @"pocket-tts serve"]];
    [task launch];
    self.isRunning = NO;
    [self setupMenu];
    [self updateIcon];
}

- (void)selectVoice:(NSMenuItem *)sender {
    self.currentVoice = sender.title;
    [self saveSettings];
    [self setupMenu];
}

- (void)selectPersona:(NSMenuItem *)sender {
    self.currentPersona = sender.title;
    [self saveSettings];
    [self setupMenu];
}

- (void)terminate:(id)sender {
    [NSApp terminate:sender];
}

@end

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        PocketTTSManager *manager = [[PocketTTSManager alloc] init];
        app.delegate = manager;
        [app setActivationPolicy:NSApplicationActivationPolicyAccessory];
        [app run];
    }
    return 0;
}

