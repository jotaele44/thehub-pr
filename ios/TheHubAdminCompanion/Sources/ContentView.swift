import SwiftUI

@MainActor
final class CompanionViewModel: ObservableObject {
    @Published private(set) var capabilities: CompanionCapabilities?
    @Published private(set) var statuses: [FederationStatus] = []
    @Published private(set) var error: String?
    private let client: AdminCompanionClient

    init(client: AdminCompanionClient) { self.client = client }

    func refresh() async {
        do {
            async let capabilities = client.capabilities()
            async let statuses = client.federationStatus()
            self.capabilities = try await capabilities
            self.statuses = try await statuses
            self.error = nil
        } catch {
            self.capabilities = nil
            self.statuses = []
            self.error = "The administrative companion is unavailable or its contract was rejected."
        }
    }
}

struct ContentView: View {
    @StateObject var model: CompanionViewModel

    var body: some View {
        NavigationStack {
            List {
                Section("Security boundary") {
                    LabeledContent("Mode", value: "Read-only companion")
                    LabeledContent("Default", value: model.capabilities?.defaultEffect ?? "DENY")
                    LabeledContent("Workstation access", value: "Disabled")
                }
                if let error = model.error {
                    Section("Unavailable") { Text(error).foregroundStyle(.secondary) }
                } else {
                    Section("Federation") {
                        ForEach(model.statuses) { item in
                            VStack(alignment: .leading) {
                                Text(item.name ?? item.id).font(.headline)
                                Text(item.status ?? "UNKNOWN").foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .navigationTitle("TheHub Admin")
            .task { await model.refresh() }
            .refreshable { await model.refresh() }
        }
    }
}
