plugins { id("com.android.application") }
android {
    namespace = "io.github.xairdrop17.mishareprobe"
    compileSdk = 36
    buildToolsVersion = "36.0.0"
    defaultConfig {
        applicationId = "io.github.xairdrop17.mishareprobe"
        minSdk = 35
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
dependencies { compileOnly("io.github.libxposed:api:102.0.0") }
tasks.register("prepareProbeDependencies") {
    doLast { configurations.getByName("debugCompileClasspath").resolve() }
}
