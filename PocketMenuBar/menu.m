#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>

@interface PocketTTSManager : NSObject <NSApplicationDelegate>
@property (strong) NSStatusItem *statusItem;
@property (strong) NSTimer *timer;
@property (assign) BOOL isRunning;
@property (assign) BOOL headphonesOnly;
@property (strong) NSString *projectPath;
@property (strong) NSArray *voices;
@property (strong) NSString *currentVoice;
@end

@implementation PocketTTSManager

- (instancetype)init {
    self = [super init];
    if (self) {
        // Try to find project path dynamically
        NSString *bundlePath = [[NSBundle mainBundle] bundlePath];
        // If we are running from build/PocketTTSBar.app, project root is 3 levels up
        // PocketMenuBar/build/PocketTTSBar.app -> 1: build, 2: PocketMenuBar, 3: root
        NSString *path = [bundlePath stringByDeletingLastPathComponent]; // build/
        path = [path stringByDeletingLastPathComponent]; // PocketMenuBar/
        path = [path stringByDeletingLastPathComponent]; // root
        
        // Verify if it looks like the project root (e.g. has pocket-say)
        NSString *checkPath = [path stringByAppendingPathComponent:@"pocket-say"];
        if (![[NSFileManager defaultManager] fileExistsAtPath:checkPath]) {
            // Fallback to hardcoded for now if dynamic fails, but try to be smart
            path = @"/Users/kempb/Projects/pocket-tts";
        }
        
        _projectPath = path;
        _voices = @[@"alba", @"marius", @"javert", @"jean", @"fantine", @"cosette", @"eponine", @"azelma"];
        _currentVoice = @"azelma";
        [self loadSettings];
    }
    return self;
}

- (void)applicationDidFinishLaunching:(NSNotification *)aNotification {
    self.statusItem = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];
    [self updateIcon];
    [self setupMenu];
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

    // Load Headphones Only setting
    NSString *hpPath = [self.projectPath stringByAppendingPathComponent:@".headphones_only"];
    _headphonesOnly = [[NSFileManager defaultManager] fileExistsAtPath:hpPath];
}

- (void)saveSettings {
    // Save Voice
    NSString *voicePath = [self.projectPath stringByAppendingPathComponent:@".current_voice"];
    [self.currentVoice writeToFile:voicePath atomically:YES encoding:NSUTF8StringEncoding error:nil];

    // Save Headphones Only setting
    NSString *hpPath = [self.projectPath stringByAppendingPathComponent:@".headphones_only"];
    if (self.headphonesOnly) {
        [@"1" writeToFile:hpPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    } else {
        [[NSFileManager defaultManager] removeItemAtPath:hpPath error:nil];
    }
}

- (void)setupMenu {
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
    [testItem setEnabled:self.isRunning];
    [testItem setTarget:self];
    [menu addItem:testItem];

    NSMenuItem *hpItem = [[NSMenuItem alloc] initWithTitle:@"Headphones Only" action:@selector(toggleHeadphonesOnly:) keyEquivalent:@"h"];
    [hpItem setState:self.headphonesOnly ? NSControlStateValueOn : NSControlStateValueOff];
    [hpItem setTarget:self];
    [menu addItem:hpItem];
    
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
    
    NSMenuItem *voiceSubmenu = [[NSMenuItem alloc] initWithTitle:@"Active Voice" action:nil keyEquivalent:@""];
    [voiceSubmenu setSubmenu:voiceMenu];
    [menu addItem:voiceSubmenu];
    
    [menu addItem:[NSMenuItem separatorItem]];
    [menu addItemWithTitle:@"Quit" action:@selector(terminate:) keyEquivalent:@"q"];
    
    self.statusItem.menu = menu;
}

- (void)toggleHeadphonesOnly:(NSMenuItem *)sender {
    self.headphonesOnly = !self.headphonesOnly;
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
    self.statusItem.button.title = self.isRunning ? @"🎙️" : @"🚫";
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
