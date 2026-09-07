import SwiftUI

@main
struct TheHubAdminCompanionApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView(model: CompanionViewModel(client: AdminCompanionClient()))
        }
    }
}
